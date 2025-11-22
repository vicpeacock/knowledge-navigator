"""
Simple MCP Client using the official mcp Python library
Uses AsyncExitStack to properly manage nested async context managers
"""
from contextlib import AsyncExitStack
from typing import Dict, Any, Optional, List, AsyncIterator
from app.core.config import settings
from app.core.oauth_utils import is_oauth_server, is_oauth_error
from app.core.error_utils import extract_root_error, get_error_message
import logging

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

logger = logging.getLogger(__name__)


class MCPClient:
    """
    Simple client for Docker MCP Gateway using the official mcp library
    Creates a new session for each operation to avoid async context issues
    """
    
    def __init__(self, base_url: Optional[str] = None, use_auth_token: bool = True, oauth_token: Optional[str] = None):
        # Log the input URL for debugging
        logger.debug(f"MCPClient.__init__ called with base_url={repr(base_url)}, use_auth_token={use_auth_token}, oauth_token={'present' if oauth_token else 'None'}")
        
        # Use provided URL or fallback to default
        raw_url = base_url or settings.mcp_gateway_url
        logger.debug(f"   Raw URL (after fallback): {repr(raw_url)}")
        
        # Clean up URL: remove trailing slashes
        # IMPORTANT: streamablehttp_client does NOT automatically append /mcp to the URL
        # It uses the URL exactly as provided. So we need to ensure /mcp is in the URL.
        if raw_url:
            self.base_url = raw_url.strip()
            # Remove trailing slash
            if self.base_url.endswith("/"):
                self.base_url = self.base_url[:-1]
            # Ensure /mcp is in the URL (streamablehttp_client does NOT add it automatically)
            # If URL doesn't end with /mcp, add it
            if not self.base_url.endswith("/mcp"):
                self.base_url = f"{self.base_url}/mcp"
            logger.debug(f"   Final base_url with /mcp: {self.base_url}")
        else:
            self.base_url = raw_url
        
        logger.debug(f"   Cleaned base_url: {repr(self.base_url)}")
        
        # Validate URL format
        if not self.base_url:
            error_msg = f"MCP server URL cannot be empty. Provided: {repr(base_url)}, Default: {repr(settings.mcp_gateway_url)}"
            logger.error(f"❌ {error_msg}")
            raise ValueError(error_msg)
        if not (self.base_url.startswith("http://") or self.base_url.startswith("https://")):
            error_msg = f"Invalid MCP server URL: {self.base_url}. URL must start with http:// or https://"
            logger.error(f"❌ {error_msg}")
            raise ValueError(error_msg)
        
        logger.info(f"✅ MCPClient initialized with base_url: {self.base_url}")

        # Store OAuth token separately for tool-level authentication
        # When EXTERNAL_OAUTH21_PROVIDER=true, we only pass Authorization header during tool calls,
        # not during initialize() or list_tools() (protocol-level auth is disabled)
        self.oauth_token = oauth_token
        
        # Prepare optional auth headers for MCP Gateway
        # NOTE: If MCP Gateway generates a new token on each startup, we need to either:
        # 1. Not use authentication (if gateway allows it)
        # 2. Read the token from gateway logs/endpoint after startup
        # 3. Configure gateway to use a fixed token
        # 
        # IMPORTANT: Some MCP servers (like Google Workspace MCP) use OAuth 2.1 per-user auth
        # with EXTERNAL_OAUTH21_PROVIDER=true. In this mode:
        # - Protocol-level auth (initialize/list_tools) is disabled - DON'T send Authorization header
        # - Tool-level auth is required - MUST send Authorization header only during tool calls
        self.headers: Dict[str, str] = {}
        
        # Priority 1: OAuth token (for Google Workspace MCP and other OAuth 2.1 servers)
        # For external OAuth 2.1 provider mode, we store the token but don't add it to headers yet
        # Headers will be set per-request: empty for initialize/list_tools, with Authorization for tool calls
        if oauth_token:
            # Check if this is an external OAuth 2.1 provider server
            # For external provider mode, we don't add Authorization to default headers
            # It will be added only during tool calls
            from app.core.oauth_utils import is_oauth_server
            is_oauth = is_oauth_server(self.base_url, oauth_required=False)
            if is_oauth:
                # External OAuth 2.1 provider mode - don't add Authorization to default headers
                # It will be added only during tool calls
                logger.debug(f"OAuth token stored for tool-level authentication (length: {len(oauth_token)})")
            else:
                # Regular OAuth mode - add to headers for all requests
                self.headers["Authorization"] = f"Bearer {oauth_token}"
                logger.debug(f"OAuth token configured for all requests (length: {len(oauth_token)})")
        # Priority 2: MCP Gateway token (for MCP Gateway)
        elif use_auth_token and settings.mcp_gateway_auth_token:
            # Only use MCP Gateway token if explicitly enabled and URL matches MCP Gateway
            # Check if this is the MCP Gateway (not Google Workspace MCP or other servers)
            is_mcp_gateway = (
                self.base_url == settings.mcp_gateway_url or
                "8080" in self.base_url or  # MCP Gateway default port
                "mcp-gateway" in self.base_url.lower()
            )
            if is_mcp_gateway:
                # MCP Gateway advertises Bearer auth
                self.headers["Authorization"] = f"Bearer {settings.mcp_gateway_auth_token}"
                logger.debug(f"MCP Gateway auth token configured (length: {len(settings.mcp_gateway_auth_token)})")
            else:
                logger.debug(f"Not using MCP Gateway token for {self.base_url} (different server)")
        else:
            logger.debug("No MCP Gateway auth token configured or use_auth_token=False - attempting connection without authentication")
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available MCP tools"""
        exit_stack = AsyncExitStack()
        try:
            # For external OAuth 2.1 provider mode, we don't require Authorization header
            # during initialize() or list_tools() (protocol-level auth is disabled)
            # However, the server will accept it if present (it will just ignore it)
            # Create headers for protocol-level operations
            protocol_headers = self.headers.copy()
            
            # CRITICAL FIX: Add required headers for SSE (Server-Sent Events) to avoid 406 Not Acceptable
            protocol_headers["Accept"] = "text/event-stream, application/json"
            protocol_headers["Content-Type"] = "application/json"
            
            # For external OAuth provider mode, we can optionally remove Authorization header
            # but it's not strictly necessary - the server will accept it even if not required
            if self.oauth_token and 'Authorization' in protocol_headers:
                # Check if Authorization header is from OAuth token (not MCP Gateway)
                auth_header = protocol_headers.get('Authorization', '')
                if auth_header == f"Bearer {self.oauth_token}":
                    # Optionally remove OAuth token for protocol-level operations
                    # (but server will accept it anyway, so we can keep it)
                    # del protocol_headers['Authorization']
                    logger.debug(f"OAuth token present in headers for list_tools() (server will accept it even if not required)")
            
            # Log headers being sent (but not the token value for security)
            logger.info(f"🔌 Connecting to MCP server at {self.base_url}")
            logger.info(f"   Headers being sent: {list(protocol_headers.keys())} (token present: {'Authorization' in protocol_headers})")
            if 'Authorization' in protocol_headers:
                logger.info(f"   Authorization header format: Bearer <token> (length: {len(protocol_headers['Authorization'])})")
            else:
                if self.oauth_token:
                    logger.info(f"   ℹ️  OAuth token available but not sent during list_tools() (external provider mode)")
                else:
                    logger.warning(f"   ⚠️  No Authorization header! Token configured: {bool(settings.mcp_gateway_auth_token)}")
            
            # Use AsyncExitStack to properly manage nested context managers
            # This ensures all cleanup happens in the same task context
            transport = await exit_stack.enter_async_context(
                streamablehttp_client(self.base_url, headers=protocol_headers)
            )
            read_stream, write_stream, session_info = transport
            
            session = await exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
            
            await session.initialize()
            response = await session.list_tools()
            
            tools = []
            for tool in response.tools:
                tools.append({
                    "name": tool.name,
                    "description": tool.description or "",
                    "inputSchema": tool.inputSchema if hasattr(tool, 'inputSchema') else {},
                })
            
            logger.info(f"✅ Retrieved {len(tools)} tools")
            return tools
            
        except Exception as e:
            # Extract the real error from ExceptionGroup/TaskGroup if present
            real_error = extract_root_error(e)
            error_message = get_error_message(real_error)
            
            # Check if this is an expected OAuth 2.1 server error
            is_oauth = is_oauth_server(self.base_url, oauth_required=False)
            
            if is_oauth and is_oauth_error(error_message):
                # This is expected for OAuth 2.1 servers before user authentication
                logger.info(f"ℹ️  OAuth 2.1 server requires user authentication (expected): {self.base_url}")
                logger.debug(f"   Error: {error_message}")
            else:
                # Log full error details for debugging (real errors)
                logger.error(f"❌ Error listing tools from {self.base_url}: {error_message}", exc_info=True)
                logger.error(f"   Error type: {type(real_error).__name__}")
                logger.error(f"   Headers sent: {list(self.headers.keys())}")
                logger.error(f"   Use auth token: {bool(self.headers.get('Authorization'))}")
                
                # Check for HTTP errors (401, 403, etc.)
                if hasattr(real_error, 'response') or '401' in error_message or 'unauthorized' in error_message.lower():
                    logger.error(f"❌ MCP Gateway authentication error: {error_message}")
                    logger.error(f"   Base URL: {self.base_url}")
                    logger.error(f"   Headers present: {list(self.headers.keys())}")
                    logger.error(f"   Token configured: {bool(settings.mcp_gateway_auth_token)}")
                    if settings.mcp_gateway_auth_token:
                        logger.error(f"   Token preview: {settings.mcp_gateway_auth_token[:20]}...")
            
            # Raise with a more informative message
            raise ValueError(f"Error connecting to MCP server at {self.base_url}: {error_message}") from real_error
        finally:
            # Properly close all context managers in the same task
            await exit_stack.aclose()
    
    async def call_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        stream: bool = False,
    ) -> Dict[str, Any]:
        """Call an MCP tool"""
        if stream:
            raise ValueError("Streaming not supported. Use call_tool_stream() instead.")
        
        exit_stack = AsyncExitStack()
        try:
            # For external OAuth 2.1 provider mode:
            # - Protocol-level auth (initialize/list_tools) is disabled - server doesn't require Authorization
            # - Tool-level auth is required - server requires Authorization header in tool call requests
            # 
            # IMPORTANT: streamablehttp_client applies headers to ALL requests (including initialize())
            # We MUST initialize WITHOUT Authorization header, then pass it only for tool calls
            # However, streamablehttp_client applies headers to all requests, so we need to:
            # 1. Initialize WITHOUT Authorization header (protocol-level auth disabled)
            # 2. Pass Authorization header during tool calls (tool-level auth required)
            #
            # Since we can't change headers mid-session, we need to initialize with empty headers,
            # then somehow add Authorization for tool calls. Unfortunately, the MCP library doesn't
            # support per-request headers. We need to initialize with headers WITHOUT Authorization,
            # and the server should accept Authorization during tool calls even if we pass it during initialize().
            #
            # Actually, let's try initializing WITHOUT Authorization header first (as per documentation)
            # Create headers WITHOUT OAuth token for initialize() (protocol-level auth disabled)
            init_headers = self.headers.copy()
            if self.oauth_token and 'Authorization' in init_headers:
                # Remove OAuth token from headers for initialize() (external provider mode requirement)
                auth_header = init_headers.get('Authorization', '')
                if auth_header == f"Bearer {self.oauth_token}":
                    del init_headers['Authorization']
                    logger.debug(f"Removed OAuth token from headers for initialize() (external provider mode)")
            
            # Create headers WITH OAuth token for tool calls (tool-level auth required)
            # CRITICAL FIX: Add required headers for SSE (Server-Sent Events) to avoid 406 Not Acceptable
            # The server requires Accept: text/event-stream for SSE connections
            tool_headers = self.headers.copy()
            
            # Add required headers for SSE (these are essential to avoid 406 errors)
            tool_headers["Accept"] = "text/event-stream, application/json"
            tool_headers["Content-Type"] = "application/json"
            
            if self.oauth_token:
                # Always include OAuth token in Authorization header for tool calls
                tool_headers["Authorization"] = f"Bearer {self.oauth_token}"
                logger.debug(f"Prepared OAuth token for tool call: {tool_name}")
            
            # IMPORTANT: For external OAuth 2.1 provider mode:
            # - Protocol-level auth (initialize/list_tools) is disabled - server doesn't require Authorization
            # - Tool-level auth is required - server requires Authorization header in tool call requests
            # 
            # The server will accept Authorization during initialize() even if not required (it will ignore it).
            # The real issue was missing Accept header causing 406 Not Acceptable errors.
            # 
            # streamablehttp_client applies headers to ALL requests (including initialize()),
            # but this is fine because the server accepts Authorization during initialize() even if not required.
            
            logger.info(f"🔌 Connecting to MCP server for tool call")
            logger.info(f"   Base URL: {self.base_url}")
            logger.info(f"   Headers being sent: {list(tool_headers.keys())}")
            logger.info(f"   OAuth token present: {bool(self.oauth_token)}")
            if 'Accept' in tool_headers:
                logger.info(f"   Accept header: {tool_headers['Accept']}")
            if 'Content-Type' in tool_headers:
                logger.info(f"   Content-Type header: {tool_headers['Content-Type']}")
            if 'Authorization' in tool_headers:
                logger.info(f"   Authorization header: Bearer <token> (length: {len(tool_headers['Authorization'])})")
            
            # Use base_url which now includes /mcp (added in __init__)
            # streamablehttp_client uses the URL exactly as provided, so we must include /mcp
            target_url = self.base_url
            logger.debug(f"   streamablehttp_client will use URL: {target_url}")
            
            transport = await exit_stack.enter_async_context(
                streamablehttp_client(target_url, headers=tool_headers)
            )
            read_stream, write_stream, session_info = transport
            
            session = await exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
            
            # Initialize - Authorization header will be sent (server might accept it even if not required)
            await session.initialize()
            
            # Call tool - Authorization header will be sent (required for external provider mode)
            result = await session.call_tool(tool_name, parameters)
            
            # Convert result to dict
            if hasattr(result, 'content'):
                content_list = result.content
                texts = []
                for item in content_list:
                    if hasattr(item, 'text'):
                        texts.append(item.text)
                    elif isinstance(item, str):
                        texts.append(item)
                    elif isinstance(item, dict):
                        texts.append(str(item))
                
                result_dict = {
                    "content": "\n".join(texts) if texts else "",
                    "isError": getattr(result, 'isError', False),
                }
            else:
                result_dict = {"result": str(result)}
            
            return result_dict
            
        except Exception as e:
            # Extract the real error from ExceptionGroup/TaskGroup if present
            real_error = extract_root_error(e)
            error_message = get_error_message(real_error)
            
            logger.error(f"❌ Error calling tool {tool_name}: {error_message}", exc_info=True)
            logger.error(f"   Base URL: {self.base_url}")
            logger.error(f"   Headers sent: {list(self.headers.keys())}")
            logger.error(f"   OAuth token stored: {bool(self.oauth_token)}")
            logger.error(f"   OAuth token in headers: {'Authorization' in self.headers}")
            if self.oauth_token:
                logger.error(f"   OAuth token length: {len(self.oauth_token)}")
                logger.error(f"   OAuth token preview: {self.oauth_token[:30]}...")
            if 'Authorization' in self.headers:
                auth_header = self.headers['Authorization']
                logger.error(f"   Authorization header length: {len(auth_header)}")
                logger.error(f"   Authorization header preview: {auth_header[:50]}...")
            
            # Check for specific HTTP errors (404, 406) that indicate configuration issues
            error_str = str(error_message).lower()
            if "404" in error_str or "not found" in error_str:
                logger.error(f"   ❌ HTTP 404: Endpoint MCP non trovato a {self.base_url}")
                logger.error(f"   Verifica che l'URL sia corretto e che il server MCP sia in esecuzione")
                logger.error(f"   L'URL dovrebbe essere: http://host:port (senza /mcp o /sse)")
            elif "406" in error_str or "not acceptable" in error_str:
                logger.error(f"   ❌ HTTP 406: Errore di negoziazione del contenuto")
                logger.error(f"   Verifica che gli header Accept e Content-Type siano corretti")
                logger.error(f"   Richiesti: Accept: text/event-stream, application/json")
            elif "session terminated" in error_str:
                logger.error(f"   ❌ Session terminated: La sessione è stata chiusa dal server")
                logger.error(f"   Questo può essere causato da:")
                logger.error(f"   - URL errato (404) o header mancanti (406)")
                logger.error(f"   - Problemi di autenticazione (401/403)")
                logger.error(f"   - Timeout o errori del server")
            
            # Check if this is an OAuth error
            from app.core.oauth_utils import is_oauth_server, is_oauth_error
            is_oauth = is_oauth_server(self.base_url, oauth_required=False)
            if is_oauth and is_oauth_error(error_message):
                logger.error(f"   This appears to be an OAuth authentication error")
            
            raise ValueError(f"Error calling MCP tool {tool_name}: {error_message}") from real_error
        finally:
            # Properly close all context managers in the same task
            await exit_stack.aclose()
    
    async def call_tool_stream(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
    ) -> AsyncIterator[Dict[str, Any]]:
        """Call tool with streaming (currently returns single chunk)"""
        result = await self.call_tool(tool_name, parameters, stream=False)
        yield result
    
    async def close(self):
        """Close client and cleanup (no-op since we create new sessions each time)"""
        # No cleanup needed since we create new sessions for each operation
        pass
