"""
Integration tests for refactored tool_manager OAuth handling
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from uuid import uuid4
from app.core.tool_manager import ToolManager
from app.core.oauth_utils import is_oauth_error


class TestToolManagerRefactored:
    """Test refactored tool_manager OAuth handling"""
    
    @pytest.fixture
    def mock_db(self):
        """Create a mock database session"""
        db = AsyncMock()
        return db
    
    @pytest.fixture
    def tool_manager(self, mock_db):
        """Create a ToolManager instance"""
        tenant_id = uuid4()
        return ToolManager(db=mock_db, tenant_id=tenant_id)
    
    @pytest.fixture
    def mock_integration(self):
        """Create a mock MCP integration"""
        integration = Mock()
        integration.id = uuid4()
        integration.enabled = True
        integration.service_type = "mcp_server"
        integration.session_metadata = {
            "server_url": "http://localhost:8003",
            "oauth_required": True,
            "oauth_credentials": {}
        }
        return integration
    
    @pytest.fixture
    def mock_user(self):
        """Create a mock user"""
        user = Mock()
        user.id = uuid4()
        user.user_metadata = {}
        return user
    
    @pytest.mark.asyncio
    async def test_execute_mcp_tool_oauth_error_handling(self, tool_manager, mock_integration, mock_user, mock_db):
        """Test OAuth error handling in execute_mcp_tool"""
        from app.services.oauth_token_manager import OAuthTokenManager
        from app.models.database import Session as SessionModel
        
        session_id = uuid4()
        
        # Mock session query to return user
        mock_session = Mock()
        mock_session.user_id = mock_user.id
        
        # Mock the database execute to return different results based on query
        async def mock_execute(query):
            """Mock execute that returns different results based on query type"""
            # Check if query is for Integration
            if hasattr(query, 'column_descriptions') or 'Integration' in str(query):
                mock_result = Mock()
                mock_result.scalars.return_value.all.return_value = [mock_integration]
                return mock_result
            # Check if query is for Session
            elif 'Session' in str(query) or 'session' in str(query).lower():
                mock_result = Mock()
                mock_result.scalar_one_or_none.return_value = mock_session
                return mock_result
            # Check if query is for User
            elif 'User' in str(query) or 'user' in str(query).lower():
                mock_result = Mock()
                mock_result.scalar_one_or_none.return_value = mock_user
                return mock_result
            else:
                mock_result = Mock()
                mock_result.scalars.return_value.all.return_value = []
                return mock_result
        
        mock_db.execute = AsyncMock(side_effect=mock_execute)
        
        # Mock MCP client to raise OAuth error
        mock_client = AsyncMock()
        mock_client.list_tools = AsyncMock(return_value=[{"name": "test_tool"}])
        mock_client.call_tool = AsyncMock(side_effect=ValueError("401 Unauthorized"))
        
        with patch("app.api.integrations.mcp._get_mcp_client_for_integration", return_value=mock_client):
            with patch.object(OAuthTokenManager, "handle_oauth_error", new_callable=AsyncMock) as mock_handle:
                mock_handle.return_value = {
                    "error": "OAuth authentication required",
                    "oauth_required": True,
                }
                
                # _execute_mcp_tool gets user from session via session_id
                result = await tool_manager._execute_mcp_tool(
                    "test_tool",
                    {},
                    mock_db,
                    session_id=session_id,
                )
                
                assert "oauth_required" in result or "error" in result
                # OAuthTokenManager.handle_oauth_error should be called when OAuth error occurs
                mock_handle.assert_called_once()
    
    def test_oauth_error_detection(self):
        """Test OAuth error detection in tool_manager context"""
        assert is_oauth_error("401 Unauthorized") is True
        assert is_oauth_error("Session terminated") is True
        assert is_oauth_error("Connection refused") is False

