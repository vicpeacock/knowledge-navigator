"""
Patch script v3 to modify auth/external_oauth_provider.py to return a permissive token during initialize().

This patch modifies ExternalOAuthProvider to return a dummy/permissive AccessToken during initialize()
instead of None, so FastMCP accepts the session even if token validation fails.
"""
import os
import logging

logger = logging.getLogger(__name__)

def apply_patch(provider_file_path: str) -> bool:
    """
    Apply patch to auth/external_oauth_provider.py to return permissive token during initialize().
    
    Args:
        provider_file_path: Path to auth/external_oauth_provider.py file
        
    Returns:
        True if patch was applied successfully, False otherwise
    """
    try:
        with open(provider_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if patch already applied
        if "Permissive token for initialize()" in content:
            logger.info("Patch v3 already applied to auth/external_oauth_provider.py")
            return True
        
        # Find the error handling that returns None and modify it to return a permissive token
        old_return_none = """                else:
                    logger.error("Could not get user info from access token")
                    return None

            except Exception as e:
                # For external OAuth provider mode, be permissive during initialize()
                # If token validation fails, log but don't block - let FastMCP handle it
                logger.debug(f"Token validation failed (may be during initialize()): {e}")
                # Return None to indicate token is not valid, but don't block the request
                # FastMCP will proceed without authentication if this is during initialize()
                return None"""
        
        new_return_permissive = """                else:
                    logger.error("Could not get user info from access token")
                    # For external OAuth provider mode, return a permissive token instead of None
                    # This allows FastMCP to accept the session during initialize() even if validation fails
                    # The token will be validated again during tool calls where it's actually required
                    logger.debug("Returning permissive token for initialize() - validation will happen during tool calls")
                    from types import SimpleNamespace
                    scope_list = list(getattr(self, "required_scopes", []) or [])
                    permissive_token = SimpleNamespace(
                        token=token,
                        scopes=scope_list,
                        expires_at=int(time.time()) + 3600,  # Default to 1-hour validity
                        claims={"email": "unknown", "sub": "unknown"},
                        client_id=self._client_id,
                        email="unknown",
                        sub="unknown"
                    )
                    return permissive_token

            except Exception as e:
                # For external OAuth provider mode, be permissive during initialize()
                # If token validation fails, return a permissive token instead of None
                # This allows FastMCP to accept the session during initialize()
                # The token will be validated again during tool calls where it's actually required
                logger.debug(f"Token validation failed (may be during initialize()): {e}")
                logger.debug("Returning permissive token for initialize() - validation will happen during tool calls")
                from types import SimpleNamespace
                import time
                scope_list = list(getattr(self, "required_scopes", []) or [])
                permissive_token = SimpleNamespace(
                    token=token,
                    scopes=scope_list,
                    expires_at=int(time.time()) + 3600,  # Default to 1-hour validity
                    claims={"email": "unknown", "sub": "unknown"},
                    client_id=self._client_id,
                    email="unknown",
                    sub="unknown"
                )
                return permissive_token"""
        
        if old_return_none in content:
            content = content.replace(old_return_none, new_return_permissive)
            
            with open(provider_file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.info("✅ Patch v3 applied successfully to auth/external_oauth_provider.py")
            return True
        else:
            logger.warning("Could not find target text in auth/external_oauth_provider.py - checking current content")
            # Check if already patched
            if "Permissive token for initialize()" in content:
                logger.info("File already has permissive token logic")
                return True
            return False
            
    except Exception as e:
        logger.error(f"Error applying patch v3 to auth/external_oauth_provider.py: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        provider_file_path = sys.argv[1]
    else:
        # Default path
        provider_file_path = "/app/auth/external_oauth_provider.py"
    
    success = apply_patch(provider_file_path)
    sys.exit(0 if success else 1)

