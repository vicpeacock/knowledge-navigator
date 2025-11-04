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
from app.models.database import Integration as IntegrationModel
from app.models.schemas import Integration, IntegrationCreate, IntegrationUpdate
from app.core.mcp_client import MCPClient
from app.core.config import settings

router = APIRouter()


def _get_mcp_client_for_integration(integration: IntegrationModel) -> MCPClient:
    """Create MCP client for a specific integration"""
    # Get server URL from integration metadata or credentials
    server_url = None
    if integration.session_metadata and "server_url" in integration.session_metadata:
        server_url = integration.session_metadata["server_url"]
    elif integration.credentials_encrypted:
        # Fallback: use credentials_encrypted as URL (for simple cases)
        server_url = integration.credentials_encrypted
    
    if not server_url:
        server_url = settings.mcp_gateway_url  # Default
    
    # Create client with custom URL
    client = MCPClient()
    client.base_url = server_url
    return client


from pydantic import BaseModel


class MCPConnectRequest(BaseModel):
    server_url: str
    name: str = "MCP Server"


@router.post("/connect")
async def connect_mcp_server(
    request: MCPConnectRequest,
    db: AsyncSession = Depends(get_db),
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
):
    """Get available tools from an MCP integration"""
    result = await db.execute(
        select(IntegrationModel)
        .where(IntegrationModel.id == integration_id)
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
        
        try:
            tools = await client.list_tools()
            logger.info(f"list_tools() returned: type={type(tools)}, length={len(tools) if isinstance(tools, list) else 'N/A'}")
        except Exception as list_error:
            logger.error(f"Error in list_tools(): {list_error}", exc_info=True)
            raise
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
        
        # Get selected tools from metadata
        # session_metadata is JSONB, ensure it's a dict
        metadata = integration.session_metadata
        if metadata is None:
            metadata = {}
        elif not isinstance(metadata, dict):
            # JSONB might be returned as a string or other type, convert it
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse session_metadata as JSON: {metadata}")
                    metadata = {}
            else:
                logger.warning(f"session_metadata is not a dict: {type(metadata)}, value: {metadata}")
                metadata = {}
        
        selected_tools = metadata.get("selected_tools", [])
        
        logger.info(f"Retrieved selected_tools for integration {integration_id}: {selected_tools} (type: {type(selected_tools)}, length: {len(selected_tools) if isinstance(selected_tools, list) else 'N/A'})")
        logger.info(f"Full metadata: {metadata}")
        
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
):
    """Select which MCP tools to enable for this integration"""
    result = await db.execute(
        select(IntegrationModel)
        .where(IntegrationModel.id == integration_id)
        .where(IntegrationModel.service_type == "mcp_server")
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
                    .where(IntegrationModel.id == integration_id)
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
        
        # Update metadata with selected tools (metadata already loaded above)
        # Create a new dict to ensure SQLAlchemy detects the change
        new_metadata = dict(metadata)  # Copy the existing metadata
        new_metadata["selected_tools"] = request.tool_names
        
        logger.info(f"Saving selected_tools for integration {integration_id}: {request.tool_names} (count: {len(request.tool_names)})")
        logger.info(f"Full metadata being saved: {new_metadata}")
        
        # Use explicit UPDATE statement to ensure JSONB is saved correctly
        # This is more reliable than modifying the object directly with AsyncSession
        await db.execute(
            update(IntegrationModel)
            .where(IntegrationModel.id == integration_id)
            .values(session_metadata=new_metadata)
        )
        await db.commit()
        
        # Refresh to get the updated object
        await db.refresh(integration)
        
        # Verify the save worked by reading from database
        await db.refresh(integration)
        saved_metadata = integration.session_metadata or {}
        
        # Handle case where session_metadata might be a string or other type
        if not isinstance(saved_metadata, dict):
            if isinstance(saved_metadata, str):
                try:
                    saved_metadata = json.loads(saved_metadata)
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse saved metadata as JSON: {saved_metadata}")
                    saved_metadata = {}
            else:
                logger.error(f"Saved metadata is not a dict: {type(saved_metadata)}, value: {saved_metadata}")
                saved_metadata = {}
        
        saved_selected = saved_metadata.get("selected_tools", [])
        logger.info(f"Verified saved selected_tools: {saved_selected} (count: {len(saved_selected) if isinstance(saved_selected, list) else 0})")
        
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
):
    """List all MCP integrations"""
    result = await db.execute(
        select(IntegrationModel)
        .where(IntegrationModel.service_type == "mcp_server")
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


@router.delete("/integrations/{integration_id}")
async def delete_mcp_integration(
    integration_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete an MCP integration"""
    result = await db.execute(
        select(IntegrationModel)
        .where(IntegrationModel.id == integration_id)
        .where(IntegrationModel.service_type == "mcp_server")
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
):
    """Debug endpoint to see raw MCP responses"""
    import logging
    logger = logging.getLogger(__name__)
    
    result = await db.execute(
        select(IntegrationModel)
        .where(IntegrationModel.id == integration_id)
        .where(IntegrationModel.service_type == "mcp_server")
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
        
        # Test connection first
        import httpx
        test_client = httpx.AsyncClient(timeout=5.0)
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
        try:
            init_response = await client.client.post(
                f"{client.base_url}/mcp",
                json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                timeout=10.0
            )
            debug_info["initialize"] = {
                "status": init_response.status_code,
                "response": init_response.json()
            }
        except httpx.ConnectError as ce:
            debug_info["initialize"] = {
                "error": f"Connection error: {str(ce)}",
                "suggestion": "The MCP server is not reachable. Check: 1) Is it running? 2) Is the URL correct? 3) Is the port exposed?"
            }
        except Exception as e:
            debug_info["initialize"] = {"error": str(e)}
        
        # Test tools/list
        try:
            tools_response = await client.client.post(
                f"{client.base_url}/mcp",
                json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                timeout=10.0
            )
            debug_info["tools_list"] = {
                "status": tools_response.status_code,
                "response": tools_response.json()
            }
        except httpx.ConnectError as ce:
            debug_info["tools_list"] = {
                "error": f"Connection error: {str(ce)}",
                "suggestion": "The MCP server is not reachable. Check: 1) Is it running? 2) Is the URL correct? 3) Is the port exposed?"
            }
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
):
    """Test connection to MCP server"""
    import logging
    logger = logging.getLogger(__name__)
    
    result = await db.execute(
        select(IntegrationModel)
        .where(IntegrationModel.id == integration_id)
        .where(IntegrationModel.service_type == "mcp_server")
    )
    integration = result.scalar_one_or_none()
    
    if not integration:
        raise HTTPException(status_code=404, detail="MCP integration not found")
    
    try:
        client = _get_mcp_client_for_integration(integration)
        
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

