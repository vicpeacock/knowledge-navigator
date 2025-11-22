"""
OAuth Token Manager - Centralized OAuth token retrieval and refresh
"""
import asyncio
import logging
from typing import Optional, Dict, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified
import httpx

from app.models.database import Integration as IntegrationModel, User
from app.core.config import settings
from app.api.integrations.mcp import _decrypt_credentials, _encrypt_credentials
from app.core.exceptions import (
    OAuthTokenExpiredError,
    OAuthAuthenticationRequiredError,
    OAuthTokenRefreshError,
)
from app.core.oauth_utils import is_oauth_error

logger = logging.getLogger(__name__)

# Locks for serializing token refresh per integration+user
_refresh_locks: Dict[str, asyncio.Lock] = {}
_locks_lock = asyncio.Lock()


async def _get_refresh_lock(integration_id: str, user_id: str) -> asyncio.Lock:
    """Get or create a lock for token refresh (prevents concurrent refreshes)"""
    lock_key = f"{integration_id}_{user_id}"
    
    async with _locks_lock:
        if lock_key not in _refresh_locks:
            _refresh_locks[lock_key] = asyncio.Lock()
        return _refresh_locks[lock_key]


class OAuthTokenManager:
    """Manages OAuth token retrieval and refresh for MCP integrations"""
    
    @staticmethod
    async def get_valid_token(
        integration: IntegrationModel,
        user: User,
        db: AsyncSession,
        auto_refresh: bool = True,
    ) -> Optional[str]:
        """
        Get a valid OAuth access token for the user, refreshing if needed.
        
        Args:
            integration: The MCP integration
            user: The user requesting the token
            db: Database session
            auto_refresh: If True, automatically refresh expired tokens
            
        Returns:
            Access token if available, None if authentication required
            
        Raises:
            OAuthTokenExpiredError: If token expired and refresh failed
            OAuthAuthenticationRequiredError: If no token available
        """
        session_metadata = integration.session_metadata or {}
        oauth_credentials = session_metadata.get("oauth_credentials", {})
        user_id_str = str(user.id)
        
        if user_id_str not in oauth_credentials:
            logger.info(f"No OAuth credentials found for user {user.id} in integration {integration.id}")
            raise OAuthAuthenticationRequiredError(
                str(integration.id),
                "OAuth authentication required. Please go to the Integrations page and click 'Authorize OAuth'."
            )
        
        try:
            encrypted_creds = oauth_credentials[user_id_str]
            credentials = _decrypt_credentials(encrypted_creds, settings.credentials_encryption_key)
            access_token = credentials.get("token")
            refresh_token = credentials.get("refresh_token")
            token_created_at = credentials.get("token_created_at")  # Timestamp when token was created
            
            if access_token:
                # Check if token might be expired (Google tokens typically expire after 1 hour)
                from datetime import datetime, timezone, timedelta
                if token_created_at:
                    try:
                        created_time = datetime.fromisoformat(token_created_at.replace('Z', '+00:00'))
                        # Google access tokens expire after 1 hour
                        # Check if token is older than 50 minutes (refresh proactively)
                        if datetime.now(timezone.utc) - created_time > timedelta(minutes=50):
                            logger.info(f"OAuth token is older than 50 minutes, attempting refresh...")
                            if refresh_token and auto_refresh:
                                try:
                                    return await OAuthTokenManager.refresh_token(integration, user, db)
                                except (OAuthTokenRefreshError, OAuthAuthenticationRequiredError) as refresh_err:
                                    logger.warning(f"Token refresh failed: {refresh_err}")
                                    raise OAuthAuthenticationRequiredError(
                                        str(integration.id),
                                        "Your Google OAuth token has expired. Please go to your Profile page and click 'Re-authorize' to refresh your authentication."
                                    )
                            else:
                                raise OAuthAuthenticationRequiredError(
                                    str(integration.id),
                                    "Your Google OAuth token has expired. Please go to your Profile page and click 'Re-authorize' to refresh your authentication."
                                )
                    except (ValueError, TypeError) as parse_error:
                        logger.debug(f"Could not parse token_created_at: {parse_error}, using token as-is")
                
                # Token exists and seems valid - return it (if expired, will be caught on first use)
                logger.debug(f"Retrieved OAuth access token for user {user.id}")
                return access_token
            elif refresh_token and auto_refresh:
                # No access token but have refresh token - try to refresh
                logger.info(f"No access token but refresh token available, attempting refresh...")
                return await OAuthTokenManager.refresh_token(integration, user, db)
            else:
                # No access token and no refresh token or auto_refresh disabled
                logger.warning(f"No access token available for user {user.id}")
                raise OAuthAuthenticationRequiredError(
                    str(integration.id),
                    "OAuth authentication required. Please go to your Profile page and click 'Re-authorize' to authenticate with your Google account."
                )
        except (OAuthTokenExpiredError, OAuthAuthenticationRequiredError):
            raise
        except Exception as e:
            logger.error(f"Error retrieving OAuth token: {e}", exc_info=True)
            raise OAuthAuthenticationRequiredError(
                str(integration.id),
                f"Error retrieving OAuth credentials: {str(e)}"
            )
    
    @staticmethod
    async def refresh_token(
        integration: IntegrationModel,
        user: User,
        db: AsyncSession,
    ) -> str:
        """
        Refresh OAuth access token using refresh token.
        
        This method is thread-safe and prevents concurrent refreshes for the same integration+user.
        
        Args:
            integration: The MCP integration
            user: The user
            db: Database session
            
        Returns:
            New access token
            
        Raises:
            OAuthTokenRefreshError: If refresh fails
            OAuthAuthenticationRequiredError: If no refresh token available
        """
        integration_id_str = str(integration.id)
        user_id_str = str(user.id)
        
        # Get lock to prevent concurrent refreshes
        lock = await _get_refresh_lock(integration_id_str, user_id_str)
        
        async with lock:
            # Double-check: another coroutine might have refreshed while we waited
            session_metadata = integration.session_metadata or {}
            oauth_credentials = session_metadata.get("oauth_credentials", {})
            
            if user_id_str not in oauth_credentials:
                raise OAuthAuthenticationRequiredError(
                    integration_id_str,
                    "No OAuth credentials found. Please re-authenticate."
                )
            
            try:
                encrypted_creds = oauth_credentials[user_id_str]
                credentials = _decrypt_credentials(encrypted_creds, settings.credentials_encryption_key)
                refresh_token = credentials.get("refresh_token")
                
                if not refresh_token:
                    raise OAuthTokenRefreshError(
                        integration_id_str,
                        user_id_str,
                        "No refresh token available"
                    )
                
                token_uri = credentials.get("token_uri", "https://oauth2.googleapis.com/token")
                client_id = credentials.get("client_id", settings.google_oauth_client_id)
                client_secret = credentials.get("client_secret", settings.google_oauth_client_secret)
                
                logger.info(f"Refreshing OAuth token for user {user.id}, integration {integration.id}")
                
                # Refresh token with timeout
                try:
                    async with httpx.AsyncClient(timeout=10.0) as http_client:
                        refresh_response = await http_client.post(
                            token_uri,
                            data={
                                "client_id": client_id,
                                "client_secret": client_secret,
                                "refresh_token": refresh_token,
                                "grant_type": "refresh_token",
                            },
                        )
                        
                        if refresh_response.status_code == 200:
                            token_data = refresh_response.json()
                            new_access_token = token_data.get("access_token")
                            
                            if new_access_token:
                                # Update credentials with new access token
                                from datetime import datetime, timezone
                                credentials["token"] = new_access_token
                                credentials["token_created_at"] = datetime.now(timezone.utc).isoformat()  # Update creation time
                                
                                # Save updated credentials back to database
                                encrypted_updated = _encrypt_credentials(
                                    credentials,
                                    settings.credentials_encryption_key
                                )
                                
                                # Refresh session metadata from DB to ensure we have latest
                                await db.refresh(integration)
                                session_metadata = integration.session_metadata or {}
                                if "oauth_credentials" not in session_metadata:
                                    session_metadata["oauth_credentials"] = {}
                                
                                session_metadata["oauth_credentials"][user_id_str] = encrypted_updated
                                integration.session_metadata = session_metadata
                                flag_modified(integration, "session_metadata")
                                
                                await db.commit()
                                await db.refresh(integration)
                                
                                logger.info(f"✅ Token refreshed successfully for user {user.id}")
                                return new_access_token
                            else:
                                raise OAuthTokenRefreshError(
                                    integration_id_str,
                                    user_id_str,
                                    "Token refresh response missing access_token"
                                )
                        else:
                            error_text = refresh_response.text[:200]
                            raise OAuthTokenRefreshError(
                                integration_id_str,
                                user_id_str,
                                f"Token refresh failed: {refresh_response.status_code} - {error_text}"
                            )
                except asyncio.TimeoutError:
                    raise OAuthTokenRefreshError(
                        integration_id_str,
                        user_id_str,
                        "Token refresh timed out after 10 seconds"
                    )
                except httpx.RequestError as e:
                    raise OAuthTokenRefreshError(
                        integration_id_str,
                        user_id_str,
                        f"Network error during token refresh: {str(e)}"
                    )
            except (OAuthTokenRefreshError, OAuthAuthenticationRequiredError):
                raise
            except Exception as e:
                logger.error(f"Error refreshing OAuth token: {e}", exc_info=True)
                raise OAuthTokenRefreshError(
                    integration_id_str,
                    user_id_str,
                    f"Unexpected error: {str(e)}"
                )
    
    @staticmethod
    async def handle_oauth_error(
        error: Exception,
        integration: IntegrationModel,
        user: Optional[User],
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """
        Handle OAuth-related errors and attempt refresh if appropriate.
        
        Args:
            error: The exception that occurred
            integration: The MCP integration
            user: The user (if available)
            db: Database session
            
        Returns:
            Error response dict with oauth_required flag
        """
        error_msg = str(error).lower()
        
        if not is_oauth_error(error_msg):
            # Not an OAuth error, return generic error
            return {"error": f"Error: {str(error)}"}
        
        if not user:
            return {
                "error": "OAuth authentication required. Please go to the Integrations page and click 'Authorize OAuth'.",
                "oauth_required": True,
                "integration_id": str(integration.id),
            }
        
        # Check if we have credentials and can try refresh
        session_metadata = integration.session_metadata or {}
        oauth_credentials = session_metadata.get("oauth_credentials", {})
        user_id_str = str(user.id)
        
        if user_id_str in oauth_credentials:
            try:
                encrypted_creds = oauth_credentials[user_id_str]
                credentials = _decrypt_credentials(encrypted_creds, settings.credentials_encryption_key)
                refresh_token = credentials.get("refresh_token")
                
                if refresh_token:
                    # Try to refresh token
                    try:
                        new_token = await OAuthTokenManager.refresh_token(integration, user, db)
                        logger.info(f"Token refreshed successfully after error, returning success")
                        # Return success - caller should retry the operation
                        return {
                            "token_refreshed": True,
                            "message": "Token refreshed, please retry the operation",
                        }
                    except OAuthTokenRefreshError as refresh_error:
                        logger.warning(f"Token refresh failed: {refresh_error.reason}")
                        return {
                            "error": "OAuth token expired and refresh failed. Please go to the Integrations page and click 'Authorize OAuth' again to re-authenticate.",
                            "oauth_required": True,
                            "token_expired": True,
                            "refresh_failed": True,
                            "integration_id": str(integration.id),
                        }
                else:
                    return {
                        "error": "OAuth token expired. Please go to the Integrations page and click 'Authorize OAuth' again to refresh your authentication.",
                        "oauth_required": True,
                        "token_expired": True,
                        "integration_id": str(integration.id),
                    }
            except Exception as decrypt_error:
                logger.warning(f"Error decrypting credentials: {decrypt_error}")
                return {
                    "error": "OAuth authentication required. Please go to the Integrations page and click 'Authorize OAuth'.",
                    "oauth_required": True,
                    "integration_id": str(integration.id),
                }
        else:
            return {
                "error": "OAuth authentication required. Please go to the Integrations page and click 'Authorize OAuth' for the Google Workspace MCP server to authenticate with your Google account.",
                "oauth_required": True,
                "integration_id": str(integration.id),
            }

