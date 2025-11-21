"""
Custom Exceptions for OAuth and MCP Integration
"""
from typing import Optional
from uuid import UUID


class OAuthTokenExpiredError(Exception):
    """OAuth token expired and refresh failed"""
    
    def __init__(self, integration_id: str, user_id: str, message: Optional[str] = None):
        self.integration_id = integration_id
        self.user_id = user_id
        self.message = message or "OAuth token expired and refresh failed"
        super().__init__(self.message)


class OAuthAuthenticationRequiredError(Exception):
    """OAuth authentication required"""
    
    def __init__(self, integration_id: str, message: Optional[str] = None):
        self.integration_id = integration_id
        self.message = message or "OAuth authentication required"
        super().__init__(self.message)


class OAuthTokenRefreshError(Exception):
    """Error refreshing OAuth token"""
    
    def __init__(self, integration_id: str, user_id: str, reason: str):
        self.integration_id = integration_id
        self.user_id = user_id
        self.reason = reason
        message = f"Failed to refresh OAuth token: {reason}"
        super().__init__(message)

