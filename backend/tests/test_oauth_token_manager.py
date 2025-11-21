"""
Unit tests for OAuth Token Manager
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from uuid import uuid4
from app.services.oauth_token_manager import OAuthTokenManager
from app.core.exceptions import (
    OAuthTokenExpiredError,
    OAuthAuthenticationRequiredError,
    OAuthTokenRefreshError,
)


class TestOAuthTokenManager:
    """Test OAuth Token Manager"""
    
    @pytest.fixture
    def mock_integration(self):
        """Create a mock integration"""
        integration = Mock()
        integration.id = uuid4()
        integration.session_metadata = {
            "oauth_credentials": {}
        }
        return integration
    
    @pytest.fixture
    def mock_user(self):
        """Create a mock user"""
        user = Mock()
        user.id = uuid4()
        return user
    
    @pytest.fixture
    def mock_db(self):
        """Create a mock database session"""
        db = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        return db
    
    @pytest.mark.asyncio
    async def test_get_valid_token_no_credentials(self, mock_integration, mock_user, mock_db):
        """Test get_valid_token when no credentials exist"""
        with pytest.raises(OAuthAuthenticationRequiredError) as exc_info:
            await OAuthTokenManager.get_valid_token(
                mock_integration,
                mock_user,
                mock_db,
            )
        assert str(mock_integration.id) in str(exc_info.value.integration_id)
    
    @pytest.mark.asyncio
    async def test_get_valid_token_with_token(self, mock_integration, mock_user, mock_db):
        """Test get_valid_token when token exists"""
        from app.api.integrations.mcp import _encrypt_credentials
        from app.core.config import settings
        
        credentials = {
            "token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
        
        encrypted = _encrypt_credentials(credentials, settings.credentials_encryption_key)
        mock_integration.session_metadata["oauth_credentials"][str(mock_user.id)] = encrypted
        
        token = await OAuthTokenManager.get_valid_token(
            mock_integration,
            mock_user,
            mock_db,
        )
        
        assert token == "test_access_token"
    
    @pytest.mark.asyncio
    async def test_refresh_token_success(self, mock_integration, mock_user, mock_db):
        """Test successful token refresh"""
        import httpx
        from app.api.integrations.mcp import _encrypt_credentials
        from app.core.config import settings
        from sqlalchemy.orm.attributes import flag_modified
        
        credentials = {
            "token": "old_token",
            "refresh_token": "test_refresh_token",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
        }
        
        encrypted = _encrypt_credentials(credentials, settings.credentials_encryption_key)
        mock_integration.session_metadata["oauth_credentials"][str(mock_user.id)] = encrypted
        
        # Mock httpx response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new_access_token",
        }
        
        # Mock flag_modified to avoid issues
        with patch("app.services.oauth_token_manager.flag_modified"):
            with patch("httpx.AsyncClient") as mock_client:
                mock_http = AsyncMock()
                mock_http.post = AsyncMock(return_value=mock_response)
                mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_http)
                mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
                
                new_token = await OAuthTokenManager.refresh_token(
                    mock_integration,
                    mock_user,
                    mock_db,
                )
                
                assert new_token == "new_access_token"
                mock_db.commit.assert_called_once()
                mock_db.refresh.assert_called()
    
    @pytest.mark.asyncio
    async def test_refresh_token_failure(self, mock_integration, mock_user, mock_db):
        """Test token refresh failure"""
        import httpx
        from app.api.integrations.mcp import _encrypt_credentials
        from app.core.config import settings
        
        credentials = {
            "token": "old_token",
            "refresh_token": "test_refresh_token",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
        
        encrypted = _encrypt_credentials(credentials, settings.credentials_encryption_key)
        mock_integration.session_metadata["oauth_credentials"][str(mock_user.id)] = encrypted
        
        # Mock httpx response with error
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Invalid refresh token"
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            
            with pytest.raises(OAuthTokenRefreshError) as exc_info:
                await OAuthTokenManager.refresh_token(
                    mock_integration,
                    mock_user,
                    mock_db,
                )
            assert "400" in str(exc_info.value.reason)
    
    @pytest.mark.asyncio
    async def test_handle_oauth_error_no_user(self, mock_integration, mock_db):
        """Test handle_oauth_error when no user"""
        error = ValueError("401 Unauthorized")
        
        result = await OAuthTokenManager.handle_oauth_error(
            error,
            mock_integration,
            None,
            mock_db,
        )
        
        assert result["oauth_required"] is True
        assert "authentication required" in result["error"].lower()
    
    @pytest.mark.asyncio
    async def test_handle_oauth_error_with_refresh(self, mock_integration, mock_user, mock_db):
        """Test handle_oauth_error with successful refresh"""
        import httpx
        from app.api.integrations.mcp import _encrypt_credentials
        from app.core.config import settings
        from sqlalchemy.orm.attributes import flag_modified
        
        error = ValueError("401 Unauthorized")
        
        credentials = {
            "token": "old_token",
            "refresh_token": "test_refresh_token",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
        
        encrypted = _encrypt_credentials(credentials, settings.credentials_encryption_key)
        mock_integration.session_metadata["oauth_credentials"][str(mock_user.id)] = encrypted
        
        # Mock successful refresh
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new_access_token",
        }
        
        # Mock flag_modified to avoid issues
        with patch("app.services.oauth_token_manager.flag_modified"):
            with patch("httpx.AsyncClient") as mock_client:
                mock_http = AsyncMock()
                mock_http.post = AsyncMock(return_value=mock_response)
                mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_http)
                mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
                
                result = await OAuthTokenManager.handle_oauth_error(
                    error,
                    mock_integration,
                    mock_user,
                    mock_db,
                )
                
                assert result.get("token_refreshed") is True

