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
        
        # Clean up URL: remove trailing slashes and /mcp suffix
        if raw_url:
            self.base_url = raw_url.strip()
            # Remove trailing slash
            if self.base_url.endswith("/"):
                self.base_url = self.base_url[:-1]
            # Remove /mcp suffix if present (streamable_http will add it)
            if self.base_url.endswith("/mcp"):
                self.base_url = self.base_url[:-4]
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

        # Prepare optional auth headers for MCP Gateway
        # NOTE: If MCP Gateway generates a new token on each startup, we need to either:
        # 1. Not use authentication (if gateway allows it)
        # 2. Read the token from gateway logs/endpoint after startup
        # 3. Configure gateway to use a fixed token
        # 
        # IMPORTANT: Some MCP servers (like Google Workspace MCP) use OAuth 2.1 per-user auth
        # and don't accept the MCP Gateway token. Set use_auth_token=False for those servers.
        self.headers: Dict[str, str] = {}
        
        # Priority 1: OAuth token (for Google Workspace MCP and other OAuth 2.1 servers)
        if oauth_token:
            self.headers["Authorization"] = f"Bearer {oauth_token}"
            logger.debug(f"OAuth token configured (length: {len(oauth_token)})")
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
            # Log headers being sent (but not the token value for security)
            logger.info(f"🔌 Connecting to MCP Gateway at {self.base_url}")
            logger.info(f"   Headers being sent: {list(self.headers.keys())} (token present: {'Authorization' in self.headers})")
            if 'Authorization' in self.headers:
                logger.info(f"   Authorization header format: Bearer <token> (length: {len(self.headers['Authorization'])})")
            else:
                logger.warning(f"   ⚠️  No Authorization header! Token configured: {bool(settings.mcp_gateway_auth_token)}")
            
            # Use AsyncExitStack to properly manage nested context managers
            # This ensures all cleanup happens in the same task context
            transport = await exit_stack.enter_async_context(
                streamablehttp_client(self.base_url, headers=self.headers)
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
            # Use AsyncExitStack to properly manage nested context managers
            # This ensures all cleanup happens in the same task context
            transport = await exit_stack.enter_async_context(
                streamablehttp_client(self.base_url, headers=self.headers)
            )
            read_stream, write_stream, session_info = transport
            
            session = await exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
            
            await session.initialize()
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
            logger.error(f"❌ Error calling tool {tool_name}: {e}", exc_info=True)
            raise ValueError(f"Error calling MCP tool: {str(e)}")
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
