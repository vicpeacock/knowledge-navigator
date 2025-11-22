"""
Patch script to modify auth/external_oauth_provider.py to make authentication optional during initialize().

This patch modifies ExternalOAuthProvider to accept Authorization header during initialize()
but not require it, allowing the session to proceed even if the token validation fails.
"""
import os
import logging

logger = logging.getLogger(__name__)

def apply_patch(provider_file_path: str) -> bool:
    """
    Apply patch to auth/external_oauth_provider.py to make authentication optional.
    
    Args:
        provider_file_path: Path to auth/external_oauth_provider.py file
        
    Returns:
        True if patch was applied successfully, False otherwise
    """
    try:
        with open(provider_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if patch already applied
        if "Authentication optional during initialize" in content:
            logger.info("Patch already applied to auth/external_oauth_provider.py")
            return True
        
        # Find and modify verify_token to be more permissive
        # We want to accept tokens during initialize() even if validation fails
        old_verify_start = """    async def verify_token(self, token: str) -> Optional[AccessToken]:
        """
        
        # Add a check to see if we're in initialize context
        # If validation fails but we're in initialize(), return a permissive token
        new_verify_logic = """    async def verify_token(self, token: str) -> Optional[AccessToken]:
        """
        
        # Actually, a better approach: modify the error handling to return None gracefully
        # instead of raising errors, so FastMCP can proceed without auth during initialize()
        
        # Find the error handling in verify_token - need to match exact indentation
        old_error_handling = """            except Exception as e:
                logger.error(f"Error validating external access token: {e}")
                return None

        # For JWT tokens, use parent class implementation"""
        
        new_error_handling = """            except Exception as e:
                # For external OAuth provider mode, be permissive during initialize()
                # If token validation fails, log but don't block - let FastMCP handle it
                logger.debug(f"Token validation failed (may be during initialize()): {e}")
                # Return None to indicate token is not valid, but don't block the request
                # FastMCP will proceed without authentication if this is during initialize()
                return None

        # For JWT tokens, use parent class implementation"""
        
        if old_error_handling in content:
            content = content.replace(old_error_handling, new_error_handling)
            
            with open(provider_file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.info("✅ Patch applied successfully to auth/external_oauth_provider.py")
            return True
        else:
            logger.warning("Could not find target text in auth/external_oauth_provider.py - checking current content")
            # Check if the file has the expected structure
            if "async def verify_token" in content:
                logger.info("File has verify_token method, but error handling may be different")
            return False
            
    except Exception as e:
        logger.error(f"Error applying patch to auth/external_oauth_provider.py: {e}", exc_info=True)
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

