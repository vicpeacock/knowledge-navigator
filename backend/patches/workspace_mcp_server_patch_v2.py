"""
Patch script v2 to modify core/server.py for EXTERNAL_OAUTH21_PROVIDER mode.

This patch modifies the server configuration to NOT set server.auth when EXTERNAL_OAUTH21_PROVIDER=true,
allowing initialize() to proceed without authentication. Authentication will be handled by AuthInfoMiddleware
only for tool calls, not for initialize().
"""
import os
import logging

logger = logging.getLogger(__name__)

def apply_patch(server_file_path: str) -> bool:
    """
    Apply patch to core/server.py to NOT set server.auth when EXTERNAL_OAUTH21_PROVIDER=true.
    
    Args:
        server_file_path: Path to core/server.py file
        
    Returns:
        True if patch was applied successfully, False otherwise
    """
    try:
        with open(server_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if patch v2 already applied
        if "Authentication handled by AuthInfoMiddleware for tool calls only" in content:
            logger.info("Patch v2 already applied to core/server.py")
            return True
        
        # Find and replace the section that sets server.auth = provider
        # We want to set server.auth = None instead, so initialize() doesn't require auth
        old_text = """                # For external OAuth provider mode, set the provider as auth so it accepts
                # Authorization header during initialize() even though protocol-level auth is disabled.
                # This allows clients to pass Authorization header during initialize() and use it
                # for subsequent tool calls without the server rejecting the session.
                # The provider will validate tokens during initialize() but won't require them.
                server.auth = provider
                logger.info("OAuth 2.1 enabled with EXTERNAL provider mode - protocol-level auth disabled")
                logger.info("Expecting Authorization bearer tokens in tool call headers")
                logger.info("Accepting Authorization header during initialize() (optional, for tool-level auth)")"""
        
        new_text = """                # For external OAuth provider mode, do NOT set server.auth
                # This allows initialize() to proceed without authentication (protocol-level auth disabled)
                # Authentication will be handled by AuthInfoMiddleware only for tool calls, not for initialize()
                # The middleware extracts Authorization header and validates tokens for tool calls
                server.auth = None
                logger.info("OAuth 2.1 enabled with EXTERNAL provider mode - protocol-level auth disabled")
                logger.info("Expecting Authorization bearer tokens in tool call headers")
                logger.info("Authentication handled by AuthInfoMiddleware for tool calls only (not during initialize())")"""
        
        if old_text in content:
            content = content.replace(old_text, new_text)
            
            with open(server_file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.info("✅ Patch v2 applied successfully to core/server.py")
            return True
        else:
            # Check if already using None
            if "server.auth = None" in content and "EXTERNAL provider mode" in content:
                logger.info("File already has server.auth = None for external provider mode")
                return True
            logger.warning("Could not find target text in core/server.py - patch may not be applicable")
            return False
            
    except Exception as e:
        logger.error(f"Error applying patch v2 to core/server.py: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        server_file_path = sys.argv[1]
    else:
        # Default path
        server_file_path = "/app/core/server.py"
    
    success = apply_patch(server_file_path)
    sys.exit(0 if success else 1)

