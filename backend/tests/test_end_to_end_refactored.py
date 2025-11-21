"""
End-to-end integration tests for refactored OAuth/MCP flow
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4


class TestEndToEndRefactored:
    """End-to-end tests for refactored OAuth/MCP integration"""
    
    @pytest.mark.asyncio
    async def test_oauth_flow_integration(self):
        """Test complete OAuth flow integration"""
        from app.core.oauth_utils import is_oauth_server, is_oauth_error
        from app.core.error_utils import extract_root_error, get_error_message
        from app.core.config import settings
        
        # Test 1: OAuth server detection
        assert is_oauth_server("http://localhost:8003", oauth_required=False) is True
        assert is_oauth_server("http://localhost:8080", oauth_required=False) is False
        
        # Test 2: OAuth error detection
        assert is_oauth_error("401 Unauthorized") is True
        assert is_oauth_error("Session terminated") is True
        assert is_oauth_error("Connection refused") is False
        
        # Test 3: Error extraction
        inner_error = ValueError("Inner error")
        outer_error = RuntimeError("Outer error")
        outer_error.__cause__ = inner_error
        
        extracted = extract_root_error(outer_error)
        assert extracted == inner_error
        
        message = get_error_message(outer_error)
        assert "Inner error" in message
        
        # Test 4: OAuth scopes configuration
        assert hasattr(settings, "google_workspace_oauth_scopes")
        assert isinstance(settings.google_workspace_oauth_scopes, list)
        assert len(settings.google_workspace_oauth_scopes) > 0
    
    @pytest.mark.asyncio
    async def test_mcp_client_creation_flow(self):
        """Test MCP client creation with OAuth"""
        from app.api.integrations.mcp import _get_mcp_client_for_integration
        from app.core.mcp_client import MCPClient
        from unittest.mock import Mock
        
        # Create mock integration
        integration = Mock()
        integration.id = uuid4()
        integration.session_metadata = {
            "server_url": "http://localhost:8003",
            "oauth_required": True,
            "oauth_credentials": {}
        }
        integration.credentials_encrypted = None
        
        # Test client creation without user (should work but no OAuth token)
        client = _get_mcp_client_for_integration(integration, current_user=None)
        assert isinstance(client, MCPClient)
        assert client.base_url is not None
    
    def test_exception_classes(self):
        """Test custom exception classes"""
        from app.core.exceptions import (
            OAuthTokenExpiredError,
            OAuthAuthenticationRequiredError,
            OAuthTokenRefreshError,
        )
        
        # Test OAuthTokenExpiredError
        error1 = OAuthTokenExpiredError("integration_id", "user_id")
        assert error1.integration_id == "integration_id"
        assert error1.user_id == "user_id"
        
        # Test OAuthAuthenticationRequiredError
        error2 = OAuthAuthenticationRequiredError("integration_id")
        assert error2.integration_id == "integration_id"
        
        # Test OAuthTokenRefreshError
        error3 = OAuthTokenRefreshError("integration_id", "user_id", "reason")
        assert error3.integration_id == "integration_id"
        assert error3.user_id == "user_id"
        assert error3.reason == "reason"

