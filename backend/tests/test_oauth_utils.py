"""
Unit tests for OAuth utilities
"""
import pytest
from app.core.oauth_utils import (
    is_oauth_server,
    is_google_workspace_server,
    get_oauth_error_type,
    is_oauth_error,
)


class TestOAuthServerDetection:
    """Test OAuth server detection"""
    
    def test_is_oauth_server_workspace_url(self):
        """Test detection of Google Workspace MCP server by URL"""
        assert is_oauth_server("http://localhost:8003") is True
        assert is_oauth_server("http://workspace-mcp:8003") is True
        assert is_oauth_server("http://google-workspace-mcp:8003") is True
    
    def test_is_oauth_server_with_flag(self):
        """Test detection with oauth_required flag"""
        assert is_oauth_server("http://example.com", oauth_required=True) is True
        assert is_oauth_server("http://example.com", oauth_required=False) is False
    
    def test_is_oauth_server_non_oauth(self):
        """Test that non-OAuth servers are not detected"""
        assert is_oauth_server("http://localhost:8080") is False
        assert is_oauth_server("http://mcp-gateway:8080") is False
    
    def test_is_google_workspace_server(self):
        """Test Google Workspace server detection"""
        assert is_google_workspace_server("http://localhost:8003") is True
        assert is_google_workspace_server("http://workspace-mcp:8003") is True
        assert is_google_workspace_server("http://google-workspace:8003") is True
        assert is_google_workspace_server("http://localhost:8080") is False


class TestOAuthErrorDetection:
    """Test OAuth error detection"""
    
    def test_get_oauth_error_type_session_terminated(self):
        """Test detection of session terminated error"""
        assert get_oauth_error_type("Session terminated") == "session_terminated"
        assert get_oauth_error_type("session terminated by server") == "session_terminated"
    
    def test_get_oauth_error_type_unauthorized(self):
        """Test detection of unauthorized error"""
        assert get_oauth_error_type("401 Unauthorized") == "unauthorized"
        assert get_oauth_error_type("Unauthorized access") == "unauthorized"
    
    def test_get_oauth_error_type_invalid_token(self):
        """Test detection of invalid token error"""
        assert get_oauth_error_type("Invalid token") == "invalid_token"
        assert get_oauth_error_type("Token is invalid") == "invalid_token"
    
    def test_get_oauth_error_type_authentication_required(self):
        """Test detection of authentication required error"""
        assert get_oauth_error_type("Authentication required") == "authentication_required"
    
    def test_get_oauth_error_type_none(self):
        """Test that non-OAuth errors return None"""
        assert get_oauth_error_type("Connection refused") is None
        assert get_oauth_error_type("Timeout error") is None
    
    def test_is_oauth_error(self):
        """Test is_oauth_error helper"""
        assert is_oauth_error("401 Unauthorized") is True
        assert is_oauth_error("Session terminated") is True
        assert is_oauth_error("Invalid token") is True
        assert is_oauth_error("Connection refused") is False
        assert is_oauth_error("") is False

