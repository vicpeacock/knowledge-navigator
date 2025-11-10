from typing import Optional


class IntegrationAuthError(Exception):
    """Raised when an integration requires user re-authorization."""

    def __init__(self, provider: str, reason: str, detail: Optional[str] = None):
        self.provider = provider
        self.reason = reason
        self.detail = detail or reason
        message = f"{provider} auth error: {reason}"
        if detail and detail != reason:
            message += f" ({detail})"
        super().__init__(message)

