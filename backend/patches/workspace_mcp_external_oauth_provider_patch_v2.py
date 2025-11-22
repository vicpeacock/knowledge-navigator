"""
Patch script v2 to modify auth/external_oauth_provider.py to validate tokens using direct HTTP call instead of Credentials object.

This patch modifies ExternalOAuthProvider to validate ya29.* tokens by calling Google's userinfo API directly
instead of using Credentials object which requires refresh_token and other fields.
"""
import os
import logging

logger = logging.getLogger(__name__)

def apply_patch(provider_file_path: str) -> bool:
    """
    Apply patch to auth/external_oauth_provider.py to use direct HTTP call for token validation.
    
    Args:
        provider_file_path: Path to auth/external_oauth_provider.py file
        
    Returns:
        True if patch was applied successfully, False otherwise
    """
    try:
        with open(provider_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if patch already applied
        if "requests.get('https://www.googleapis.com/oauth2/v2/userinfo'" in content:
            logger.info("Patch v2 already applied to auth/external_oauth_provider.py")
            return True
        
        # Find and replace the token validation logic
        old_validation = """            try:
                from auth.google_auth import get_user_info

                # Create minimal Credentials object for userinfo API call
                credentials = Credentials(
                    token=token,
                    token_uri="https://oauth2.googleapis.com/token",
                    client_id=self._client_id,
                    client_secret=self._client_secret
                )

                # Validate token by calling userinfo API
                user_info = get_user_info(credentials)"""
        
        new_validation = """            try:
                # Validate token by calling Google's userinfo API directly
                # This avoids the need for refresh_token and other fields required by Credentials object
                import requests
                response = requests.get(
                    'https://www.googleapis.com/oauth2/v2/userinfo',
                    headers={'Authorization': f'Bearer {token}'},
                    timeout=10
                )
                
                if response.status_code == 200:
                    user_info = response.json()
                else:
                    logger.debug(f"Token validation failed: HTTP {response.status_code}")
                    user_info = None"""
        
        if old_validation in content:
            content = content.replace(old_validation, new_validation)
            
            with open(provider_file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.info("✅ Patch v2 applied successfully to auth/external_oauth_provider.py")
            return True
        else:
            logger.warning("Could not find target text in auth/external_oauth_provider.py - checking if already patched differently")
            # Check if already using requests
            if "requests.get" in content and "userinfo" in content:
                logger.info("File already uses requests for token validation")
                return True
            return False
            
    except Exception as e:
        logger.error(f"Error applying patch v2 to auth/external_oauth_provider.py: {e}", exc_info=True)
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

