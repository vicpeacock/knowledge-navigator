"""
Integration tests for refactored MCP/OAuth code
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from uuid import uuid4
from app.api.integrations.mcp import (
    _resolve_mcp_url,
    _get_oauth_token_for_user,
    _get_mcp_client_for_integration,
)
from app.core.oauth_utils import is_oauth_server
from app.core.mcp_client import MCPClient


class TestMCPIntegrationRefactored:
    """Test refactored MCP integration code"""
    
    @pytest.fixture
    def mock_integration(self):
        """Create a mock integration"""
        integration = Mock()
        integration.id = uuid4()
        integration.session_metadata = {
            "server_url": "http://localhost:8003",
            "oauth_required": True,
            "oauth_credentials": {}
        }
        integration.credentials_encrypted = None
        return integration
    
    @pytest.fixture
    def mock_user(self):
        """Create a mock user"""
        user = Mock()
        user.id = uuid4()
        return user
    
    def test_resolve_mcp_url_default(self):
        """Test URL resolution with default"""
        url = _resolve_mcp_url(None)
        assert url is not None
        assert url.startswith("http")
    
    def test_resolve_mcp_url_localhost(self):
        """Test URL resolution with localhost"""
        url = _resolve_mcp_url("http://localhost:8003")
        assert "localhost" in url or "host.docker.internal" in url
    
    def test_get_oauth_token_for_user_no_credentials(self, mock_integration, mock_user):
        """Test getting OAuth token when no credentials exist"""
        token = _get_oauth_token_for_user(mock_integration, mock_user)
        assert token is None
    
    def test_get_oauth_token_for_user_with_token(self, mock_integration, mock_user):
        """Test getting OAuth token when credentials exist"""
        from app.api.integrations.mcp import _encrypt_credentials
        from app.core.config import settings
        
        credentials = {
            "token": "test_access_token",
            "refresh_token": "test_refresh_token",
        }
        
        encrypted = _encrypt_credentials(credentials, settings.credentials_encryption_key)
        mock_integration.session_metadata["oauth_credentials"][str(mock_user.id)] = encrypted
        
        token = _get_oauth_token_for_user(mock_integration, mock_user)
        assert token == "test_access_token"
    
    def test_get_mcp_client_for_integration_oauth_server(self, mock_integration, mock_user):
        """Test MCP client creation for OAuth server"""
        client = _get_mcp_client_for_integration(mock_integration, current_user=mock_user)
        assert isinstance(client, MCPClient)
        assert client.base_url is not None
    
    def test_get_mcp_client_for_integration_no_user(self, mock_integration):
        """Test MCP client creation without user"""
        client = _get_mcp_client_for_integration(mock_integration, current_user=None)
        assert isinstance(client, MCPClient)
    
    def test_is_oauth_server_integration(self, mock_integration):
        """Test OAuth server detection with integration metadata"""
        server_url = mock_integration.session_metadata.get("server_url", "")
        oauth_required = mock_integration.session_metadata.get("oauth_required", False)
        
        is_oauth = is_oauth_server(server_url, oauth_required)
        assert is_oauth is True  # Should be True for workspace server

