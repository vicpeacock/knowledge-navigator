"""
OAuth Utilities - Centralized OAuth server detection and configuration
"""
from typing import Optional
import logging

logger = logging.getLogger(__name__)


def is_oauth_server(server_url: str, oauth_required: bool = False) -> bool:
    """
    Determine if an MCP server is an OAuth 2.1 server (like Google Workspace MCP).
    
    Args:
        server_url: The MCP server URL
        oauth_required: Flag from integration metadata indicating OAuth is required
        
    Returns:
        True if this is an OAuth 2.1 server, False otherwise
    """
    if not server_url:
        return False
    
    server_url_lower = server_url.lower()
    
    return (
        oauth_required or
        "workspace" in server_url_lower or
        "8003" in server_url or  # Google Workspace MCP default port
        "google" in server_url_lower
    )


def is_google_workspace_server(server_url: str) -> bool:
    """
    Check if this is specifically a Google Workspace MCP server.
    
    Args:
        server_url: The MCP server URL
        
    Returns:
        True if this is Google Workspace MCP, False otherwise
    """
    if not server_url:
        return False
    
    server_url_lower = server_url.lower()
    return (
        "workspace" in server_url_lower or
        "8003" in server_url or
        "google" in server_url_lower
    )


def get_oauth_error_type(error_message: str) -> Optional[str]:
    """
    Determine the type of OAuth error from error message.
    
    Args:
        error_message: The error message (will be lowercased)
        
    Returns:
        Error type: 'session_terminated', 'unauthorized', 'invalid_token', or None
    """
    if not error_message:
        return None
    
    error_lower = error_message.lower()
    
    if "session terminated" in error_lower:
        return "session_terminated"
    elif "401" in error_lower or "unauthorized" in error_lower:
        return "unauthorized"
    elif "invalid_token" in error_lower or "token" in error_lower and "invalid" in error_lower:
        return "invalid_token"
    elif "authentication" in error_lower:
        return "authentication_required"
    
    return None


def is_oauth_error(error_message: str) -> bool:
    """
    Check if an error message indicates an OAuth-related error.
    
    Args:
        error_message: The error message
        
    Returns:
        True if this is an OAuth error, False otherwise
    """
    return get_oauth_error_type(error_message) is not None

