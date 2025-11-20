"""
MCP Integration API - Manage MCP server connections and tool selection
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from uuid import UUID
from typing import List, Dict, Any, Optional
import json

from app.db.database import get_db
from app.models.database import Integration as IntegrationModel, User
from app.models.schemas import Integration, IntegrationCreate, IntegrationUpdate
from app.core.mcp_client import MCPClient
from app.core.config import settings
from app.core.tenant_context import get_tenant_id
from app.core.user_context import get_current_user

router = APIRouter()


def _get_mcp_client_for_integration(integration: IntegrationModel) -> MCPClient:
    """Create MCP client for a specific integration"""
    import logging
    import os
    logger = logging.getLogger(__name__)
    
    # Get server URL from integration metadata or credentials
    server_url = None
    if integration.session_metadata and "server_url" in integration.session_metadata:
        server_url = integration.session_metadata["server_url"]
    elif integration.credentials_encrypted:
        # Fallback: use credentials_encrypted as URL (for simple cases)
        server_url = integration.credentials_encrypted
    
    # Detect if we're running in Docker (check for Docker-specific environment variables or files)
    is_docker = os.path.exists("/.dockerenv") or os.path.exists("/proc/self/cgroup") and "docker" in open("/proc/self/cgroup", "r").read()
    
    logger.info(f"🔍 MCP URL resolution: saved_url={server_url}, settings.mcp_gateway_url={settings.mcp_gateway_url}, is_docker={is_docker}")
    
    if not server_url:
        server_url = settings.mcp_gateway_url  # Default
        logger.info(f"   Using default URL: {server_url}")
    else:
        # Only convert if we're in Docker and saved URL uses localhost
        # OR if we're NOT in Docker and saved URL uses host.docker.internal
        if is_docker and "localhost" in server_url:
            # Running in Docker, convert localhost to host.docker.internal
            converted_url = server_url.replace("localhost", "host.docker.internal")
            logger.info(f"🔄 Converting localhost URL to Docker host URL: {server_url} -> {converted_url}")
            server_url = converted_url
        elif not is_docker and "host.docker.internal" in server_url:
            # Running locally, convert host.docker.internal to localhost
            converted_url = server_url.replace("host.docker.internal", "localhost")
            logger.info(f"🔄 Converting Docker host URL to localhost: {server_url} -> {converted_url}")
            server_url = converted_url
        else:
            logger.info(f"   Using saved URL as-is: {server_url}")
    
    logger.info(f"✅ Final MCP URL: {server_url}")
    
    # Create client with custom URL - pass it to constructor to ensure headers are set correctly
    client = MCPClient(base_url=server_url)
    return client


from pydantic import BaseModel


class MCPConnectRequest(BaseModel):
    server_url: str
    name: str = "MCP Server"


@router.post("/connect")
async def connect_mcp_server(
    request: MCPConnectRequest,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
):
    """Connect to an MCP server and discover available tools"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"Connecting to MCP server: {request.server_url}")
        # Create temporary client to test connection
        try:
            test_client = MCPClient(base_url=request.server_url)
            logger.info(f"Created MCP client with base_url: {test_client.base_url}")
            
            # Try to list tools
            logger.info("Calling list_tools()...")
            tools = await test_client.list_tools()
            logger.info(f"list_tools() returned: type={type(tools)}, length={len(tools) if isinstance(tools, list) else 'N/A'}")
            if isinstance(tools, list) and len(tools) > 0:
                logger.info(f"First tool sample: {str(tools[0])[:200]}")
            else:
                logger.warning(f"list_tools() returned empty or invalid result: {tools}")
            
            await test_client.close()
        except Exception as client_error:
            logger.error(f"Error in MCP client: {client_error}", exc_info=True)
            raise
        
        # Ensure tools is a list
        if not isinstance(tools, list):
            logger.warning(f"Tools is not a list, got: {type(tools)}, value: {str(tools)[:500]}")
            tools = []
        
        logger.info(f"Final tools count: {len(tools)}")
        
        # Store integration (use SQLAlchemy model, not Pydantic schema)
        integration = IntegrationModel(
            provider="mcp",
            service_type="mcp_server",
            credentials_encrypted=request.server_url,  # Store URL (not encrypted, but using same field)
            enabled=True,
            tenant_id=tenant_id,
            session_metadata={
                "server_url": request.server_url,
                "name": request.name,
                "selected_tools": [],  # User will select tools separately
                "available_tools": [tool.get("name", "") for tool in tools if isinstance(tool, dict) and "name" in tool],
            },
        )
        db.add(integration)
        await db.commit()
        await db.refresh(integration)
        
        logger.info(f"Integration created with ID: {integration.id}, stored {len(integration.session_metadata.get('available_tools', []))} tool names")
        
        return {
            "integration_id": str(integration.id),
            "server_url": request.server_url,
            "available_tools": tools,  # Return actual tools data, not just names
            "count": len(tools),
        }
    except Exception as e:
        logger.error(f"Error connecting to MCP server: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error connecting to MCP server: {str(e)}")


@router.get("/{integration_id}/tools")
async def get_mcp_tools(
    integration_id: UUID,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    current_user: User = Depends(get_current_user),
):
    """Get available tools from an MCP integration (with per-user selected tools)"""
    result = await db.execute(
        select(IntegrationModel)
        .where(IntegrationModel.id == integration_id)
        .where(IntegrationModel.tenant_id == tenant_id)
        .where(IntegrationModel.service_type == "mcp_server")
        .where(IntegrationModel.enabled == True)
    )
    integration = result.scalar_one_or_none()
    
    if not integration:
        raise HTTPException(status_code=404, detail="MCP integration not found")
    
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        server_url = integration.session_metadata.get('server_url', '') if integration.session_metadata else ''
        logger.info(f"Getting tools for integration {integration_id} from server: {server_url}")
        
        client = _get_mcp_client_for_integration(integration)
        logger.info(f"Created MCP client with base_url: {client.base_url}")
        logger.info(f"MCP client headers: {list(client.headers.keys())} (token configured: {bool(settings.mcp_gateway_auth_token)})")
        
        try:
            tools = await client.list_tools()
            logger.info(f"list_tools() returned: type={type(tools)}, length={len(tools) if isinstance(tools, list) else 'N/A'}")
        except Exception as list_error:
            # Extract the real error from ExceptionGroup/TaskGroup if present
            real_error = list_error
            error_message = str(list_error)
            
            # Check if it's an ExceptionGroup (Python 3.11+)
            if hasattr(list_error, 'exceptions') and len(list_error.exceptions) > 0:
                # Get the first exception from the group
                real_error = list_error.exceptions[0]
                error_message = str(real_error)
                logger.warning(f"Extracted error from ExceptionGroup: {error_message}")
            
            logger.error(f"Error in list_tools(): {error_message}", exc_info=True)
            
            # Log the full error for debugging
            error_str = error_message.lower()
            error_detail = error_message
            
            # Check if it's an authentication error
            if "401" in error_str or "unauthorized" in error_str or (hasattr(real_error, 'status_code') and real_error.status_code == 401):
                logger.warning(f"MCP Gateway authentication error. Token configured: {bool(settings.mcp_gateway_auth_token)}")
                # Re-raise the original error with a clearer message
                raise HTTPException(
                    status_code=401,
                    detail=f"MCP Gateway authentication failed: {error_detail[:200]}. Please check MCP_GATEWAY_AUTH_TOKEN configuration."
                )
            elif "connection" in error_str or "refused" in error_str or "connect" in error_str:
                raise HTTPException(
                    status_code=503,
                    detail=f"MCP Gateway is not available: {error_detail[:200]}. Please check if the gateway is running."
                )
            else:
                # For other errors, re-raise with original error details
                raise HTTPException(
                    status_code=500,
                    detail=f"MCP Gateway error: {error_detail[:200]}"
                )
        finally:
            try:
                await client.close()
            except Exception as close_error:
                logger.warning(f"Error closing client: {close_error}")
        
        # Ensure tools is a list
        if not isinstance(tools, list):
            logger.warning(f"Tools is not a list, got: {type(tools)}, value: {str(tools)[:500]}")
            tools = []
        else:
            logger.info(f"Successfully retrieved {len(tools)} tools")
            if tools:
                logger.info(f"First 5 tool names: {[tool.get('name', 'unknown') if isinstance(tool, dict) else str(tool)[:50] for tool in tools[:5]]}")
                logger.info(f"First tool structure: {json.dumps(tools[0] if tools and isinstance(tools[0], dict) else {}, indent=2)[:500]}")
            else:
                logger.warning("Tools list is empty!")
        
        # Get selected tools from user_metadata (per-user preferences)
        user_metadata = current_user.user_metadata or {}
        mcp_preferences = user_metadata.get("mcp_tools_preferences", {})
        selected_tools = mcp_preferences.get(str(integration_id), [])
        
        logger.info(f"Retrieved selected_tools for user {current_user.email}, integration {integration_id}: {selected_tools} (type: {type(selected_tools)}, length: {len(selected_tools) if isinstance(selected_tools, list) else 'N/A'})")
        
        # Ensure selected_tools is a list
        if not isinstance(selected_tools, list):
            logger.warning(f"selected_tools is not a list: {type(selected_tools)}, converting")
            selected_tools = []
        
        return {
            "integration_id": str(integration.id),
            "server_url": server_url,
            "available_tools": tools,
            "selected_tools": selected_tools,
        }
    except HTTPException:
        # Re-raise HTTPExceptions (like 503 for auth errors) as-is
        raise
    except Exception as e:
        logger.error(f"Error fetching tools from MCP integration {integration_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching tools: {str(e)}")


class SelectToolsRequest(BaseModel):
    tool_names: List[str]


@router.post("/{integration_id}/tools/select")
async def select_mcp_tools(
    integration_id: UUID,
    request: SelectToolsRequest,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    current_user: User = Depends(get_current_user),
):
    """Select which MCP tools to enable for this integration (per-user preferences)"""
    result = await db.execute(
        select(IntegrationModel)
        .where(
            IntegrationModel.id == integration_id,
            IntegrationModel.tenant_id == tenant_id,
            IntegrationModel.service_type == "mcp_server"
        )
    )
    integration = result.scalar_one_or_none()
    
    if not integration:
        raise HTTPException(status_code=404, detail="MCP integration not found")
    
    import logging
    logger = logging.getLogger(__name__)
    
    # Validate tools exist - use cached available_tools from metadata instead of calling gateway again
    # This avoids blocking the gateway with multiple rapid connections
    try:
        metadata = integration.session_metadata or {}
        available_tool_names = metadata.get("available_tools", [])
        
        if not available_tool_names:
            logger.warning(f"No cached tools in metadata for integration {integration_id}, trying to fetch...")
            # Only fetch if we don't have cached tools (shouldn't happen normally)
            client = _get_mcp_client_for_integration(integration)
            try:
                available_tools = await client.list_tools()
                available_tool_names = [tool.get("name", "") for tool in available_tools if isinstance(tool, dict)]
                # Update metadata with tools for future use
                metadata["available_tools"] = available_tool_names
                # Use explicit UPDATE statement to ensure JSONB is saved correctly
                await db.execute(
                    update(IntegrationModel)
                    .where(
                        IntegrationModel.id == integration_id,
                        IntegrationModel.tenant_id == tenant_id
                    )
                    .values(session_metadata=metadata)
                )
                await db.commit()
            finally:
                await client.close()
        
        invalid_tools = [name for name in request.tool_names if name not in available_tool_names]
        
        if invalid_tools:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid tool names: {invalid_tools}. Available: {available_tool_names[:20]}...",
            )
        
        # Save selected tools in user_metadata instead of integration metadata (per-user preferences)
        # Get current user_metadata (create a copy to ensure SQLAlchemy detects the change)
        current_metadata = current_user.user_metadata or {}
        user_metadata = dict(current_metadata)  # Create a new dict to ensure SQLAlchemy detects the change
        
        # Store MCP tools preferences as a dict: {integration_id: [tool_names]}
        if "mcp_tools_preferences" not in user_metadata:
            user_metadata["mcp_tools_preferences"] = {}
        
        # Create a new dict for mcp_tools_preferences to ensure SQLAlchemy detects the change
        mcp_prefs = dict(user_metadata.get("mcp_tools_preferences", {}))
        mcp_prefs[str(integration_id)] = request.tool_names
        user_metadata["mcp_tools_preferences"] = mcp_prefs
        
        logger.info(f"Saving selected_tools for user {current_user.email}, integration {integration_id}: {request.tool_names} (count: {len(request.tool_names)})")
        
        # Use explicit UPDATE statement to ensure JSONB is saved correctly
        # This is more reliable than modifying the object directly with AsyncSession
        await db.execute(
            update(User)
            .where(User.id == current_user.id)
            .values(user_metadata=user_metadata)
        )
        await db.commit()
        await db.refresh(current_user)
        
        # Verify the save worked by reading from user_metadata
        saved_user_metadata = current_user.user_metadata or {}
        saved_mcp_prefs = saved_user_metadata.get("mcp_tools_preferences", {})
        saved_selected = saved_mcp_prefs.get(str(integration_id), [])
        
        logger.info(f"Verified saved selected_tools for user {current_user.email}: {saved_selected} (count: {len(saved_selected) if isinstance(saved_selected, list) else 0})")
        
        # Double-check: if saved_selected is empty but we saved tools, something went wrong
        if not saved_selected and request.tool_names:
            logger.error(f"CRITICAL: Tools were not saved! Requested: {request.tool_names}, Saved: {saved_selected}")
            raise HTTPException(status_code=500, detail="Failed to save tools to database. Please try again.")
        
        return {
            "integration_id": str(integration.id),
            "selected_tools": request.tool_names,
            "message": f"Selected {len(request.tool_names)} tools",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error selecting tools: {str(e)}")


@router.get("/integrations")
async def list_mcp_integrations(
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
):
    """List all MCP integrations (for current tenant)"""
    result = await db.execute(
        select(IntegrationModel)
        .where(
            IntegrationModel.service_type == "mcp_server",
            IntegrationModel.tenant_id == tenant_id
        )
        .order_by(IntegrationModel.id.desc())
    )
    integrations = result.scalars().all()
    
    def parse_metadata(metadata):
        """Helper to parse JSONB metadata safely"""
        if metadata is None:
            return {}
        if isinstance(metadata, dict):
            return metadata
        if isinstance(metadata, str):
            try:
                return json.loads(metadata)
            except json.JSONDecodeError:
                return {}
        return {}
    
    return {
        "integrations": [
            {
                "id": str(i.id),
                "provider": i.provider,
                "service_type": i.service_type,
                "enabled": i.enabled,
                "name": parse_metadata(i.session_metadata).get("name", "MCP Server"),
                "server_url": parse_metadata(i.session_metadata).get("server_url", ""),
                "selected_tools": parse_metadata(i.session_metadata).get("selected_tools", []),
            }
            for i in integrations
        ],
    }


class MCPUpdateRequest(BaseModel):
    name: str


@router.put("/integrations/{integration_id}")
async def update_mcp_integration(
    integration_id: UUID,
    request: MCPUpdateRequest,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    current_user: User = Depends(get_current_user),
):
    """Update MCP integration name (admin only)"""
    # Check if user is admin
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can update MCP integrations")
    
    result = await db.execute(
        select(IntegrationModel)
        .where(
            IntegrationModel.id == integration_id,
            IntegrationModel.tenant_id == tenant_id,
            IntegrationModel.service_type == "mcp_server"
        )
    )
    integration = result.scalar_one_or_none()
    
    if not integration:
        raise HTTPException(status_code=404, detail="MCP integration not found")
    
    # Update name in session_metadata
    session_metadata = integration.session_metadata or {}
    session_metadata = dict(session_metadata)  # Create a copy to ensure SQLAlchemy detects the change
    session_metadata["name"] = request.name
    
    # Use explicit UPDATE statement to ensure JSONB is saved correctly
    await db.execute(
        update(IntegrationModel)
        .where(
            IntegrationModel.id == integration_id,
            IntegrationModel.tenant_id == tenant_id
        )
        .values(session_metadata=session_metadata)
    )
    await db.commit()
    await db.refresh(integration)
    
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"MCP integration {integration_id} name updated to '{request.name}' by admin {current_user.email}")
    
    return {
        "id": str(integration.id),
        "name": request.name,
        "server_url": session_metadata.get("server_url", ""),
    }


@router.delete("/integrations/{integration_id}")
async def delete_mcp_integration(
    integration_id: UUID,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
):
    """Delete an MCP integration (for current tenant)"""
    result = await db.execute(
        select(IntegrationModel)
        .where(
            IntegrationModel.id == integration_id,
            IntegrationModel.tenant_id == tenant_id,
            IntegrationModel.service_type == "mcp_server"
        )
    )
    integration = result.scalar_one_or_none()
    
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    
    await db.delete(integration)
    await db.commit()
    
    return {"message": "MCP integration deleted successfully"}


@router.get("/{integration_id}/debug")
async def debug_mcp_connection(
    integration_id: UUID,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
):
    """Debug endpoint to see raw MCP responses (for current tenant)"""
    import logging
    logger = logging.getLogger(__name__)
    
    result = await db.execute(
        select(IntegrationModel)
        .where(
            IntegrationModel.id == integration_id,
            IntegrationModel.tenant_id == tenant_id,
            IntegrationModel.service_type == "mcp_server"
        )
    )
    integration = result.scalar_one_or_none()
    
    if not integration:
        raise HTTPException(status_code=404, detail="MCP integration not found")
    
    try:
        client = _get_mcp_client_for_integration(integration)
        server_url = integration.session_metadata.get('server_url', '') if integration.session_metadata else ''
        
        # Test all endpoints
        debug_info = {
            "server_url": server_url,
            "base_url": client.base_url,
            "initialize": None,
            "tools_list": None,
        }
        
        # Prepare optional auth headers (same as MCPClient)
        import httpx
        from app.core.config import settings as app_settings
        headers = {}
        if app_settings.mcp_gateway_auth_token:
            headers["Authorization"] = f"Bearer {app_settings.mcp_gateway_auth_token}"

        # Test connection first (simple GET on base URL)
        test_client = httpx.AsyncClient(timeout=5.0, headers=headers)
        try:
            test_response = await test_client.get(f"{client.base_url}/")
            debug_info["connection_test"] = {
                "status": test_response.status_code,
                "reachable": True,
                "response_preview": test_response.text[:200]
            }
        except httpx.ConnectError as ce:
            debug_info["connection_test"] = {
                "reachable": False,
                "error": f"Connection failed: {str(ce)}",
                "suggestion": f"⚠️ The MCP server at {client.base_url} is not reachable. Possible causes:\n1. Server is not running\n2. Wrong URL/port\n3. Port is not exposed from Docker\n4. Firewall blocking connection\n\nTo fix:\n- If MCP Gateway runs in Docker, check: docker ps (should show container with port 8080)\n- If running locally, verify: curl {client.base_url}\n- Try: docker ps | grep mcp to see if container is running"
            }
        except Exception as e:
            debug_info["connection_test"] = {
                "reachable": False,
                "error": str(e)
            }
        finally:
            await test_client.aclose()
        
        # Test initialize
        # Test initialize & tools/list using MCPClient abstraction
        try:
            tools = await client.list_tools()
            debug_info["tools_list"] = {
                "status": 200,
                "count": len(tools),
                "first_tools": [t.get("name", "") for t in tools[:5]] if isinstance(tools, list) else [],
            }
            debug_info["initialize"] = {"status": 200, "message": "initialize via list_tools OK"}
        except Exception as e:
            debug_info["tools_list"] = {"error": str(e)}
        
        await client.close()
        return debug_info
    except Exception as e:
        logger.error(f"Debug failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Debug failed: {str(e)}")


@router.post("/{integration_id}/test")
async def test_mcp_connection(
    integration_id: UUID,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
):
    """Test connection to MCP server (for current tenant)"""
    import logging
    logger = logging.getLogger(__name__)
    
    result = await db.execute(
        select(IntegrationModel)
        .where(
            IntegrationModel.id == integration_id,
            IntegrationModel.tenant_id == tenant_id,
            IntegrationModel.service_type == "mcp_server"
        )
    )
    integration = result.scalar_one_or_none()
    
    if not integration:
        raise HTTPException(status_code=404, detail="MCP integration not found")
    
    try:
        # DEBUG: Log settings token
        from app.core.config import settings as debug_settings
        logger.error(f"🔍 DEBUG - settings.mcp_gateway_auth_token: {debug_settings.mcp_gateway_auth_token[:30] if debug_settings.mcp_gateway_auth_token else 'NONE'}...")
        
        client = _get_mcp_client_for_integration(integration)
        
        logger.error(f"🔍 DEBUG - client.base_url: {client.base_url}")
        logger.error(f"🔍 DEBUG - client.headers: {client.headers}")
        
        logger.info(f"Testing connection for {integration.session_metadata.get('server_url', '')}")
        
        # Test tools/list (this will handle the connection properly)
        # Don't do a separate initialize - let list_tools handle it
        tools = await client.list_tools()
        
        # Ensure client is closed properly
        try:
            await client.close()
        except Exception as close_error:
            logger.warning(f"Error closing client: {close_error}")
        
        if not isinstance(tools, list):
            logger.warning(f"Tools is not a list, got: {type(tools)}")
            tools = []
        
        return {
            "status": "connected",
            "server_url": integration.session_metadata.get("server_url", "") if integration.session_metadata else "",
            "tools_count": len(tools),
            "tools": [tool.get("name", "") if isinstance(tool, dict) else str(tool)[:50] for tool in tools[:10]] if tools else [],
        }
    except Exception as e:
        logger.error(f"Connection test failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Connection test failed: {str(e)}")

