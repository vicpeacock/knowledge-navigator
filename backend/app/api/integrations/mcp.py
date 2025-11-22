"""
MCP Integration API - Manage MCP server connections and tool selection
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm.attributes import flag_modified
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
from app.core.oauth_utils import is_oauth_server
from app.core.error_utils import extract_root_error, get_error_message
from fastapi.responses import RedirectResponse
from cryptography.fernet import Fernet
import base64
import binascii
import json
import os
import logging

router = APIRouter()


def _encrypt_credentials(credentials: Dict[str, Any], key: str) -> str:
    """Encrypt credentials for storage"""
    try:
        if not key:
            raise ValueError("Encryption key is required")
        # Ensure key is 32 bytes for Fernet
        key_bytes = key.encode()[:32].ljust(32, b'0')
        key_b64 = base64.urlsafe_b64encode(key_bytes)
        f = Fernet(key_b64)
        credentials_json = json.dumps(credentials)
        encrypted = f.encrypt(credentials_json.encode())
        return encrypted.decode()
    except Exception as e:
        raise ValueError(f"Error encrypting credentials: {str(e)}")


def _decrypt_credentials(encrypted: str, key: str) -> Dict[str, Any]:
    """Decrypt credentials from storage"""
    try:
        if not key:
            raise ValueError("Encryption key is required")
        # Ensure key is 32 bytes for Fernet
        key_bytes = key.encode()[:32].ljust(32, b'0')
        key_b64 = base64.urlsafe_b64encode(key_bytes)
        f = Fernet(key_b64)
        decrypted = f.decrypt(encrypted.encode())
        return json.loads(decrypted.decode())
    except Exception as e:
        raise ValueError(f"Error decrypting credentials: {str(e)}")


logger = logging.getLogger(__name__)


def _resolve_mcp_url(server_url: Optional[str]) -> str:
    """
    Resolve MCP server URL, handling Docker vs localhost conversion.
    
    Args:
        server_url: The server URL from integration metadata or None
        
    Returns:
        Resolved server URL
    """
    # Detect if we're running in Docker
    is_docker = (
        os.path.exists("/.dockerenv") or
        (os.path.exists("/proc/self/cgroup") and "docker" in open("/proc/self/cgroup", "r").read())
    )
    
    if not server_url:
        server_url = settings.mcp_gateway_url  # Default
        logger.info(f"   Using default URL: {server_url}")
        return server_url
    
    logger.info(f"🔍 MCP URL resolution: saved_url={server_url}, settings.mcp_gateway_url={settings.mcp_gateway_url}, is_docker={is_docker}")
    
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
    return server_url


def _get_oauth_token_for_user(
    integration: IntegrationModel,
    user: User,
) -> Optional[str]:
    """
    Get OAuth access token for user from integration (synchronous, no refresh).
    
    This is a lightweight function that just retrieves the token from storage.
    Token refresh is handled by OAuthTokenManager in async context.
    
    Args:
        integration: The MCP integration
        user: The user
        
    Returns:
        Access token if available, None otherwise
    """
    try:
        session_metadata = integration.session_metadata or {}
        oauth_credentials = session_metadata.get("oauth_credentials", {})
        user_id_str = str(user.id)
        
        if user_id_str not in oauth_credentials:
            logger.debug(f"No OAuth credentials found for user {user.id} in integration {integration.id}")
            return None
        
        encrypted_creds = oauth_credentials[user_id_str]
        try:
            credentials = _decrypt_credentials(encrypted_creds, settings.credentials_encryption_key)
            access_token = credentials.get("token")
            
            if access_token:
                logger.debug(f"Retrieved OAuth access token for user {user.id}")
                return access_token
            else:
                logger.debug(f"OAuth credentials found but no access token for user {user.id}")
                return None
        except Exception as decrypt_error:
            logger.warning(f"Could not decrypt OAuth credentials: {decrypt_error}")
            return None
    except Exception as oauth_error:
        logger.warning(f"Error retrieving OAuth token: {oauth_error}")
        return None


def _get_mcp_client_for_integration(
    integration: IntegrationModel, 
    current_user: Optional[User] = None,
    oauth_token: Optional[str] = None
) -> MCPClient:
    """
    Create MCP client for a specific integration.
    
    This function handles:
    - URL resolution (Docker vs localhost)
    - OAuth server detection
    - OAuth token retrieval (if available) or use provided token
    - MCPClient creation
    
    Args:
        integration: The MCP integration
        current_user: Optional user for OAuth token retrieval (used if oauth_token not provided)
        oauth_token: Optional pre-retrieved OAuth token (takes precedence over current_user)
        
    Returns:
        Configured MCPClient instance
    """
    # Get server URL from integration metadata or credentials
    server_url = None
    if integration.session_metadata and "server_url" in integration.session_metadata:
        server_url = integration.session_metadata["server_url"]
    elif integration.credentials_encrypted:
        # Fallback: use credentials_encrypted as URL (for simple cases)
        server_url = integration.credentials_encrypted
    
    # Resolve URL (Docker vs localhost)
    resolved_url = _resolve_mcp_url(server_url)
    
    # Check if this is an OAuth 2.1 server
    session_metadata = integration.session_metadata or {}
    oauth_required = session_metadata.get("oauth_required", False)
    is_oauth = is_oauth_server(resolved_url, oauth_required)
    use_auth_token = not is_oauth
    
    # For OAuth 2.1 servers, retrieve OAuth token if not provided
    if is_oauth and not oauth_token and current_user:
        oauth_token = _get_oauth_token_for_user(integration, current_user)
        if oauth_token:
            logger.info(f"✅ Retrieved OAuth access token for user {current_user.id}")
        else:
            logger.info(f"ℹ️  No OAuth token available for user {current_user.id} - user may need to authenticate")
    elif is_oauth and oauth_token:
        logger.info(f"✅ Using provided OAuth token")
    
    # Create client with OAuth token if available (for OAuth 2.1 servers)
    # or without token (for MCP Gateway or when no OAuth credentials available)
    client = MCPClient(base_url=resolved_url, use_auth_token=use_auth_token, oauth_token=oauth_token)
    if oauth_token:
        logger.info(f"Created MCP client with OAuth token for {resolved_url}")
    else:
        logger.info(f"Created MCP client with use_auth_token={use_auth_token} for {resolved_url}")
        if is_oauth:
            logger.debug(f"OAuth 2.1 server but no OAuth token available - user may need to authenticate")
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
        # Validate and log the server URL
        server_url = request.server_url.strip() if request.server_url else None
        logger.info(f"📡 Connecting to MCP server:")
        logger.info(f"   Raw URL from request: {repr(request.server_url)}")
        logger.info(f"   Cleaned URL: {repr(server_url)}")
        
        if not server_url:
            raise HTTPException(
                status_code=400,
                detail="Server URL non può essere vuoto. Inserisci un URL valido (es: http://localhost:8003)"
            )
        
        if not (server_url.startswith("http://") or server_url.startswith("https://")):
            raise HTTPException(
                status_code=400,
                detail=f"URL non valido: {server_url}. L'URL deve iniziare con http:// o https://"
            )
        
        # Create temporary client to test connection
        # For Google Workspace MCP and other OAuth 2.1 servers, don't use MCP Gateway token
        # They handle authentication per-user via OAuth 2.1
        is_oauth = is_oauth_server(server_url, oauth_required=False)
        use_auth_token = not is_oauth  # Don't use token for OAuth 2.1 servers
        
        logger.info(f"   Detected OAuth server: {is_oauth}")
        logger.info(f"   Use auth token: {use_auth_token}")
        
        tools = []
        oauth_required = False
        
        try:
            test_client = MCPClient(base_url=server_url, use_auth_token=use_auth_token)
            logger.info(f"✅ Created MCP client with base_url: {test_client.base_url}, use_auth_token={use_auth_token}")
            
            # Try to list tools
            # For OAuth 2.1 servers, list_tools() might fail without user authentication
            # In that case, we'll still create the integration but mark it as requiring OAuth
            logger.info("Calling list_tools()...")
            oauth_required = False
            
            try:
                tools = await test_client.list_tools()
                logger.info(f"list_tools() returned: type={type(tools)}, length={len(tools) if isinstance(tools, list) else 'N/A'}")
                if isinstance(tools, list) and len(tools) > 0:
                    logger.info(f"First tool sample: {str(tools[0])[:200]}")
                else:
                    logger.warning(f"list_tools() returned empty or invalid result: {tools}")
            except Exception as list_error:
                # For OAuth 2.1 servers (like Google Workspace MCP), listing tools requires user authentication
                # This is expected - tools will be discovered when user uses them for the first time
                from app.core.oauth_utils import is_oauth_error
                error_msg = str(list_error)
                if is_oauth and is_oauth_error(error_msg):
                    logger.warning(f"⚠️  Server requires OAuth authentication to list tools: {list_error}")
                    logger.info("   This is expected for OAuth 2.1 servers like Google Workspace MCP")
                    logger.info("   Integration will be created, but tools will be discovered when user authenticates")
                    oauth_required = True
                    tools = []  # Empty tools list - will be populated after OAuth
                else:
                    # Re-raise if it's a different error
                    logger.error(f"❌ Unexpected error listing tools: {list_error}", exc_info=True)
                    raise
            
            await test_client.close()
        except Exception as client_error:
            # Extract the real error from ExceptionGroup/TaskGroup if present
            real_error = extract_root_error(client_error)
            error_message = get_error_message(real_error)
            
            logger.error(f"Error in MCP client: {error_message}", exc_info=True)
            logger.error(f"   Error type: {type(real_error).__name__}")
            logger.error(f"   Server URL: {server_url}")
            
            # Check if this is an OAuth 2.1 server that requires authentication
            from app.core.oauth_utils import is_oauth_server, is_oauth_error
            is_oauth = is_oauth_server(server_url, oauth_required=False)
            
            # Check if it's an OAuth/authentication error
            if is_oauth and is_oauth_error(error_message):
                logger.warning(f"⚠️  OAuth authentication required (expected for OAuth 2.1 servers)")
                logger.info(f"   Server is reachable, but tools require user authentication")
                # Create integration anyway, marking it as requiring OAuth
                oauth_required = True
                tools = []  # Empty tools list - will be populated after OAuth
            else:
                # Provide a more user-friendly error message for other errors
                if "connection" in error_message or "connect" in error_message:
                    raise HTTPException(
                        status_code=503,
                        detail=f"Impossibile connettersi al server MCP all'indirizzo {server_url}. Verifica che il server sia in esecuzione e raggiungibile."
                    )
                elif "401" in error_message or "unauthorized" in error_message:
                    raise HTTPException(
                        status_code=401,
                        detail=f"Autenticazione fallita per il server MCP. Verifica le credenziali OAuth."
                    )
                else:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Errore durante la connessione al server MCP: {str(real_error)[:200]}"
                    )
        
        # Ensure tools is a list (might be empty if OAuth is required)
        if not isinstance(tools, list):
            logger.warning(f"Tools is not a list, got: {type(tools)}, value: {str(tools)[:500]}")
            tools = []
        
        logger.info(f"Final tools count: {len(tools)}, OAuth required: {oauth_required}")
        
        # Store integration (use SQLAlchemy model, not Pydantic schema)
        integration = IntegrationModel(
            provider="mcp",
            service_type="mcp_server",
            credentials_encrypted=request.server_url,  # Store URL (not encrypted, but using same field)
            enabled=True,
            tenant_id=tenant_id,
            session_metadata={
                "server_url": server_url,  # Use cleaned URL
                "name": request.name,
                "selected_tools": [],  # User will select tools separately
                "available_tools": [tool.get("name", "") for tool in tools if isinstance(tool, dict) and "name" in tool],
                "oauth_required": oauth_required,  # Mark if OAuth is required
            },
        )
        db.add(integration)
        await db.commit()
        await db.refresh(integration)
        
        logger.info(f"Integration created with ID: {integration.id}, stored {len(integration.session_metadata.get('available_tools', []))} tool names")
        
        return {
            "integration_id": str(integration.id),
            "server_url": server_url,  # Return cleaned URL
            "available_tools": tools,  # Return actual tools data, not just names
            "count": len(tools),
            "oauth_required": oauth_required,  # Inform frontend if OAuth is needed
            "message": "OAuth authentication required. Tools will be available after user authentication." if oauth_required else f"Connected successfully. Found {len(tools)} tools.",
        }
    except Exception as e:
        logger.error(f"Error connecting to MCP server: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error connecting to MCP server: {str(e)}")


@router.get("/{integration_id}/oauth/authorize")
async def authorize_mcp_oauth(
    integration_id: UUID,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    current_user: User = Depends(get_current_user),
):
    """Start OAuth2 flow for Google Workspace MCP server"""
    import logging
    logger = logging.getLogger(__name__)
    
    if not settings.google_oauth_client_id or not settings.google_oauth_client_secret:
        raise HTTPException(
            status_code=400,
            detail="Google OAuth credentials not configured. Please set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET in .env"
        )
    
    # Get integration
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
    
    session_metadata = integration.session_metadata or {}
    server_url = session_metadata.get("server_url", "")
    
    # Check if this is a Google Workspace MCP server
    from app.core.oauth_utils import is_google_workspace_server
    is_google_workspace = is_google_workspace_server(server_url)
    
    if not is_google_workspace:
        raise HTTPException(
            status_code=400,
            detail="OAuth is only available for Google Workspace MCP server"
        )
    
    try:
        from google_auth_oauthlib.flow import Flow
        
        # Create OAuth flow
        # Use a fixed redirect_uri (not dynamic with integration_id) - integration_id is passed via state
        redirect_uri = f"{settings.base_url}/api/integrations/mcp/oauth/callback"
        
        client_config = {
            "web": {
                "client_id": settings.google_oauth_client_id,
                "client_secret": settings.google_oauth_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect_uri]
            }
        }
        
        # Scopes for Google Workspace
        scopes = settings.google_workspace_oauth_scopes
        
        flow = Flow.from_client_config(
            client_config,
            scopes=scopes,
            redirect_uri=redirect_uri
        )
        
        # Encode state with integration_id and user_id
        state_payload = {
            "integration_id": str(integration_id),
            "user_id": str(current_user.id),
        }
        state_str = base64.urlsafe_b64encode(
            json.dumps(state_payload).encode("utf-8")
        ).decode("utf-8")
        
        # Always use 'consent' prompt to force re-authorization if needed
        # This allows users to re-authenticate and update permissions
        authorization_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent',  # Force consent screen even if already authorized
            state=state_str,
        )
        
        logger.info(f"OAuth authorization URL generated for integration {integration_id}, user {current_user.id}")
        
        return {"authorization_url": authorization_url}
    except Exception as e:
        logger.error(f"Error creating OAuth flow: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error creating OAuth flow: {str(e)}")


@router.delete("/{integration_id}/oauth/revoke")
async def revoke_mcp_oauth(
    integration_id: UUID,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    current_user: User = Depends(get_current_user),
):
    """Revoke OAuth credentials for the current user for a specific MCP integration"""
    import logging
    logger = logging.getLogger(__name__)
    
    # Get integration
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
    
    session_metadata = integration.session_metadata or {}
    user_id_str = str(current_user.id)
    
    # Remove OAuth credentials for this user
    if "oauth_credentials" in session_metadata:
        oauth_credentials = session_metadata.get("oauth_credentials", {})
        if user_id_str in oauth_credentials:
            del oauth_credentials[user_id_str]
            session_metadata["oauth_credentials"] = oauth_credentials
            integration.session_metadata = session_metadata
            flag_modified(integration, "session_metadata")
            await db.commit()
            await db.refresh(integration)
            logger.info(f"✅ OAuth credentials revoked for user {current_user.email} (id: {user_id_str})")
            return {"message": "OAuth credentials revoked successfully"}
        else:
            logger.warning(f"No OAuth credentials found for user {current_user.email}")
            return {"message": "No OAuth credentials found for this user"}
    else:
        logger.warning(f"No OAuth credentials stored for this integration")
        return {"message": "No OAuth credentials found"}


@router.get("/oauth/callback")
async def mcp_oauth_callback(
    code: str,
    state: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    current_user: Optional[User] = Depends(get_current_user),
):
    """OAuth2 callback for Google Workspace MCP server"""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"🔵 OAuth callback called!")
    logger.info(f"   Code: {code[:20]}... (length: {len(code)})")
    logger.info(f"   State: {state[:50] if state else 'None'}...")
    logger.info(f"   Tenant ID: {tenant_id}")
    logger.info(f"   Current user from session: {current_user.email if current_user else 'None'} (ID: {current_user.id if current_user else 'None'})")
    
    if not settings.google_oauth_client_id or not settings.google_oauth_client_secret:
        raise HTTPException(
            status_code=400,
            detail="Google OAuth credentials not configured"
        )
    
    try:
        from google_auth_oauthlib.flow import Flow
        
        # Decode state to get integration_id and user_id FIRST (before using integration_id)
        integration_id: Optional[UUID] = None
        user_id: Optional[UUID] = None
        
        logger.info(f"🔍 Decoding state parameter...")
        logger.info(f"   State value: {state}")
        logger.info(f"   State length: {len(state) if state else 0}")
        logger.info(f"   State type: {type(state)}")
        
        if state:
            try:
                logger.info(f"   Attempting base64 decode...")
                state_bytes = state.encode("utf-8")
                missing_padding = len(state_bytes) % 4
                if missing_padding:
                    logger.info(f"   Adding {4 - missing_padding} padding bytes")
                    state_bytes += b'=' * (4 - missing_padding)
                
                decoded = base64.urlsafe_b64decode(state_bytes)
                logger.info(f"   Decoded bytes length: {len(decoded)}")
                logger.info(f"   Decoded bytes preview: {decoded[:100]}")
                
                payload_str = decoded.decode("utf-8")
                logger.info(f"   Decoded string: {payload_str}")
                
                payload = json.loads(payload_str)
                logger.info(f"   Parsed JSON payload: {payload}")
                
                integration_id_str = payload.get("integration_id")
                user_id_str = payload.get("user_id")
                
                logger.info(f"   Extracted integration_id_str: {integration_id_str}")
                logger.info(f"   Extracted user_id_str: {user_id_str}")
                
                if integration_id_str:
                    integration_id = UUID(integration_id_str)
                    logger.info(f"✅ OAuth callback - Decoded integration_id: {integration_id}")
                if user_id_str:
                    user_id = UUID(user_id_str)
                    logger.info(f"✅ OAuth callback - Decoded user_id: {user_id}")
            except binascii.Error as e:
                logger.error(f"❌ Base64 decode error: {e}")
                logger.error(f"   State value: {state}")
                raise HTTPException(status_code=400, detail=f"Invalid state parameter: base64 decode failed - {str(e)}")
            except json.JSONDecodeError as e:
                logger.error(f"❌ JSON decode error: {e}")
                logger.error(f"   Decoded string: {decoded.decode('utf-8', errors='replace')}")
                raise HTTPException(status_code=400, detail=f"Invalid state parameter: JSON decode failed - {str(e)}")
            except ValueError as e:
                logger.error(f"❌ UUID parse error: {e}")
                logger.error(f"   integration_id_str: {integration_id_str}")
                logger.error(f"   user_id_str: {user_id_str}")
                raise HTTPException(status_code=400, detail=f"Invalid state parameter: UUID parse failed - {str(e)}")
            except Exception as e:
                logger.error(f"❌ Unexpected error decoding state: {e}", exc_info=True)
                raise HTTPException(status_code=400, detail=f"Invalid state parameter: {str(e)}")
        else:
            logger.error(f"❌ State parameter is None or empty")
            raise HTTPException(status_code=400, detail="State parameter is required")
        
        if not integration_id:
            logger.error(f"❌ integration_id is None after decoding")
            raise HTTPException(status_code=400, detail="Invalid state parameter: integration_id is required")
        
        # CRITICAL FIX: If user_id is not in state or is None, use current_user from session
        # This ensures we always save credentials for the correct user
        if not user_id:
            if current_user:
                user_id = current_user.id
                logger.warning(f"⚠️  user_id not found in state, using current_user from session: {user_id}")
            else:
                logger.error(f"❌ user_id is None and no current_user available in callback")
                raise HTTPException(status_code=400, detail="User ID is required but not found in state or session")
        
        # Get integration (now that we have integration_id from state)
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
        
        # Create OAuth flow and fetch token
        # Use the same fixed redirect_uri as in authorize endpoint
        redirect_uri = f"{settings.base_url}/api/integrations/mcp/oauth/callback"
        
        client_config = {
            "web": {
                "client_id": settings.google_oauth_client_id,
                "client_secret": settings.google_oauth_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect_uri]
            }
        }
        
        scopes = settings.google_workspace_oauth_scopes
        
        flow = Flow.from_client_config(
            client_config,
            scopes=scopes,
            redirect_uri=redirect_uri
        )
        
        flow.fetch_token(code=code)
        
        credentials = {
            "token": flow.credentials.token,
            "refresh_token": flow.credentials.refresh_token,
            "token_uri": flow.credentials.token_uri,
            "client_id": flow.credentials.client_id,
            "client_secret": flow.credentials.client_secret,
            "scopes": flow.credentials.scopes,
        }
        
        # Save credentials (encrypted) in session_metadata per user
        session_metadata = integration.session_metadata or {}
        
        # Store OAuth credentials per user in session_metadata
        if "oauth_credentials" not in session_metadata:
            session_metadata["oauth_credentials"] = {}
        
        # Ensure we have a valid user_id (should be set by now from state or current_user)
        if not user_id:
            logger.error(f"❌ user_id is still None after all checks")
            raise HTTPException(status_code=400, detail="User ID is required but not found")
        
        user_id_str = str(user_id)
        logger.info(f"🔐 Encrypting OAuth credentials for user_id_str: {user_id_str}")
        logger.info(f"   User email (if available): {current_user.email if current_user else 'Not available'}")
        logger.info(f"   Credentials keys: {list(credentials.keys())}")
        logger.info(f"   Token preview: {credentials.get('token', '')[:20]}...")
        
        try:
            encrypted_credentials = _encrypt_credentials(credentials, settings.credentials_encryption_key)
            logger.info(f"✅ Credentials encrypted successfully (length: {len(encrypted_credentials)})")
        except Exception as encrypt_error:
            logger.error(f"❌ Error encrypting credentials: {encrypt_error}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Error encrypting credentials: {str(encrypt_error)}")
        
        # Store credentials
        if "oauth_credentials" not in session_metadata:
            session_metadata["oauth_credentials"] = {}
        session_metadata["oauth_credentials"][user_id_str] = encrypted_credentials
        logger.info(f"📝 Storing credentials in session_metadata['oauth_credentials']['{user_id_str}']")
        logger.info(f"   Total OAuth users: {list(session_metadata['oauth_credentials'].keys())}")
        
        # Update integration
        integration.session_metadata = session_metadata
        # IMPORTANT: Flag the JSONB field as modified so SQLAlchemy detects the change
        flag_modified(integration, "session_metadata")
        if user_id and (not integration.user_id or integration.user_id != user_id):
            integration.user_id = user_id
            logger.info(f"✅ Updated integration.user_id to {user_id}")
        
        try:
            await db.commit()
            logger.info(f"✅ Database commit successful")
        except Exception as commit_error:
            logger.error(f"❌ Error committing to database: {commit_error}", exc_info=True)
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Error saving credentials: {str(commit_error)}")
        
        await db.refresh(integration)
        
        # Verify credentials were saved
        refreshed_metadata = integration.session_metadata or {}
        refreshed_oauth = refreshed_metadata.get("oauth_credentials", {})
        if user_id_str in refreshed_oauth:
            logger.info(f"✅ Verified: OAuth credentials saved successfully for user {user_id_str}")
            logger.info(f"   Stored credentials length: {len(refreshed_oauth[user_id_str])}")
        else:
            logger.error(f"❌ ERROR: OAuth credentials NOT found after commit and refresh!")
            logger.error(f"   Expected key: {user_id_str}")
            logger.error(f"   Available keys: {list(refreshed_oauth.keys())}")
            raise HTTPException(status_code=500, detail="Failed to save OAuth credentials - verification failed")
        
        logger.info(f"✅ OAuth credentials saved for integration {integration_id}, user {user_id}")
        
        # Try to fetch tools now that we have OAuth credentials
        # We need to get the user from the database to pass to _get_mcp_client_for_integration
        try:
            if user_id:
                from app.models.database import User as UserModel
                user_result = await db.execute(
                    select(UserModel).where(UserModel.id == user_id)
                )
                user = user_result.scalar_one_or_none()
                if user:
                    client = _get_mcp_client_for_integration(integration, current_user=user)
                    tools = await client.list_tools()
                    logger.info(f"Successfully retrieved {len(tools)} tools after OAuth")
                    
                    # Update available_tools in metadata
                    session_metadata = integration.session_metadata or {}
                    session_metadata["available_tools"] = [tool.get("name", "") for tool in tools if isinstance(tool, dict) and "name" in tool]
                    integration.session_metadata = session_metadata
                    await db.commit()
                else:
                    logger.warning(f"User {user_id} not found, cannot fetch tools after OAuth")
            else:
                logger.warning("No user_id in OAuth callback, cannot fetch tools")
        except Exception as tools_error:
            logger.warning(f"Could not fetch tools after OAuth: {tools_error}", exc_info=True)
            # Continue anyway - tools will be discovered when used
        
        # Redirect to frontend Profile page (where OAuth authorization is managed)
        frontend_url = settings.frontend_url or "http://localhost:3003"
        redirect_url = f"{frontend_url}/settings/profile?oauth_success=true&integration_id={integration_id}"
        logger.info(f"✅ OAuth callback completed successfully, redirecting to: {redirect_url}")
        return RedirectResponse(url=redirect_url)
    except Exception as e:
        logger.error(f"❌ Error in OAuth callback: {e}", exc_info=True)
        logger.error(f"   Exception type: {type(e).__name__}")
        logger.error(f"   Exception args: {e.args}")
        raise HTTPException(status_code=500, detail=f"Error in OAuth callback: {str(e)}")


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
        
        client = _get_mcp_client_for_integration(integration, current_user=current_user)
        logger.info(f"Created MCP client with base_url: {client.base_url}")
        logger.info(f"MCP client headers: {list(client.headers.keys())} (token configured: {bool(settings.mcp_gateway_auth_token)})")
        if "Authorization" in client.headers:
            auth_header = client.headers["Authorization"]
            logger.info(f"   Authorization header present: {auth_header[:30]}... (length: {len(auth_header)})")
        else:
            logger.info(f"   No Authorization header in client")
        
        # For OAuth 2.1 servers, tools may not be available until user authenticates with the MCP server
        # Try to get tools, but if it fails with auth error, return empty list (user will authenticate when using tools)
        tools = []
        try:
            tools = await client.list_tools()
            logger.info(f"list_tools() returned: type={type(tools)}, length={len(tools) if isinstance(tools, list) else 'N/A'}")
        except Exception as list_error:
            # Extract the real error from ExceptionGroup/TaskGroup if present
            real_error = extract_root_error(list_error)
            error_message = get_error_message(real_error)
            error_str = error_message.lower()
            error_detail = error_message
            
            # Check if this is an OAuth 2.1 server
            from app.core.oauth_utils import is_oauth_server, is_oauth_error
            session_metadata_check = integration.session_metadata or {}
            oauth_required = session_metadata_check.get("oauth_required", False)
            is_oauth = is_oauth_server(server_url, oauth_required)
            
            # For OAuth 2.1 servers, "Session terminated" is expected if user hasn't authenticated yet
            # The user will authenticate when they first use a tool
            if is_oauth and is_oauth_error(error_message):
                logger.info(f"⚠️  OAuth 2.1 server requires user authentication (expected behavior)")
                logger.info(f"   Tools will be available after user authenticates when using a tool for the first time")
                tools = []  # Return empty list - user will authenticate when using tools
            elif "401" in error_str or "unauthorized" in error_str or (hasattr(real_error, 'status_code') and real_error.status_code == 401):
                # For non-OAuth servers, authentication errors are real errors
                logger.error(f"Error in list_tools(): {error_message}", exc_info=True)
                logger.warning(f"MCP Gateway authentication error. Token configured: {bool(settings.mcp_gateway_auth_token)}")
                raise HTTPException(
                    status_code=401,
                    detail=f"MCP Gateway authentication failed: {error_detail[:200]}. Please check MCP_GATEWAY_AUTH_TOKEN configuration."
                )
            elif "connection" in error_str or "refused" in error_str or "connect" in error_str:
                logger.error(f"Error in list_tools(): {error_message}", exc_info=True)
                raise HTTPException(
                    status_code=503,
                    detail=f"MCP Gateway is not available: {error_detail[:200]}. Please check if the gateway is running."
                )
            else:
                # For other errors, log and re-raise
                logger.error(f"Error in list_tools(): {error_message}", exc_info=True)
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
            client = _get_mcp_client_for_integration(integration, current_user=current_user)
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
                "oauth_required": parse_metadata(i.session_metadata).get("oauth_required", False),
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
        client = _get_mcp_client_for_integration(integration, current_user=current_user)
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
    current_user: User = Depends(get_current_user),
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
    
    session_metadata = integration.session_metadata or {}
    server_url = session_metadata.get("server_url", "")
    oauth_required = session_metadata.get("oauth_required", False)
    
    # Check if this is an OAuth 2.1 server
    is_oauth = is_oauth_server(server_url, oauth_required)
    
    try:
        client = _get_mcp_client_for_integration(integration, current_user=current_user)
        
        logger.info(f"Testing connection for {server_url}")
        logger.info(f"   OAuth required: {oauth_required}, Is OAuth server: {is_oauth_server}")
        
        # For OAuth 2.1 servers, list_tools() might fail without user authentication
        # In that case, we'll return a success status but indicate OAuth is needed
        tools = []
        try:
            tools = await client.list_tools()
            if not isinstance(tools, list):
                logger.warning(f"Tools is not a list, got: {type(tools)}")
                tools = []
        except Exception as list_error:
            from app.core.oauth_utils import is_oauth_error
            error_msg = str(list_error)
            # Check if it's an OAuth/authentication error
            if is_oauth and is_oauth_error(error_msg):
                logger.info(f"⚠️  OAuth 2.1 server requires user authentication (expected behavior)")
                logger.info(f"   Server is reachable, but tools require user authentication")
                logger.info(f"   User will authenticate when using a tool for the first time")
                return {
                    "status": "connected",
                    "oauth_required": True,
                    "server_url": server_url,
                    "tools_count": 0,
                    "tools": [],
                    "message": "Server is reachable. OAuth 2.1 authentication required. User will authenticate automatically when using a tool for the first time.",
                }
            else:
                # Re-raise if it's a different error or not an OAuth server
                logger.error(f"Connection test failed: {list_error}", exc_info=True)
                raise
        
        # Ensure client is closed properly
        try:
            await client.close()
        except Exception as close_error:
            logger.warning(f"Error closing client: {close_error}")
        
        return {
            "status": "connected",
            "server_url": server_url,
            "tools_count": len(tools),
            "tools": [tool.get("name", "") if isinstance(tool, dict) else str(tool)[:50] for tool in tools[:10]] if tools else [],
            "oauth_required": oauth_required,
        }
    except Exception as e:
        logger.error(f"Connection test failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Connection test failed: {str(e)}")

