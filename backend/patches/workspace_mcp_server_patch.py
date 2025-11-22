"""
Patch script to modify core/server.py for EXTERNAL_OAUTH21_PROVIDER mode.

This patch modifies the server configuration to accept Authorization header
during initialize() even when protocol-level auth is disabled. This allows
clients to pass Authorization header during initialize() and use it for
subsequent tool calls without the server rejecting the session.
"""
import os
import logging

logger = logging.getLogger(__name__)

def apply_patch(server_file_path: str) -> bool:
    """
    Apply patch to core/server.py to accept Authorization during initialize()
    when EXTERNAL_OAUTH21_PROVIDER=true.
    
    Args:
        server_file_path: Path to core/server.py file
        
    Returns:
        True if patch was applied successfully, False otherwise
    """
    try:
        with open(server_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if patch already applied
        if "Accepting Authorization header during initialize()" in content:
            logger.info("Patch already applied to core/server.py")
            return True
        
        # Find and replace the problematic section
        old_text = """                # Disable protocol-level auth, expect bearer tokens in tool calls
                server.auth = None
                logger.info("OAuth 2.1 enabled with EXTERNAL provider mode - protocol-level auth disabled")
                logger.info("Expecting Authorization bearer tokens in tool call headers")"""
        
        new_text = """                # For external OAuth provider mode, set the provider as auth so it accepts
                # Authorization header during initialize() even though protocol-level auth is disabled.
                # This allows clients to pass Authorization header during initialize() and use it
                # for subsequent tool calls without the server rejecting the session.
                # The provider will validate tokens during initialize() but won't require them.
                server.auth = provider
                logger.info("OAuth 2.1 enabled with EXTERNAL provider mode - protocol-level auth disabled")
                logger.info("Expecting Authorization bearer tokens in tool call headers")
                logger.info("Accepting Authorization header during initialize() (optional, for tool-level auth)")"""
        
        if old_text in content:
            content = content.replace(old_text, new_text)
            
            with open(server_file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.info("✅ Patch applied successfully to core/server.py")
            return True
        else:
            logger.warning("Could not find target text in core/server.py - patch may not be applicable")
            return False
            
    except Exception as e:
        logger.error(f"Error applying patch to core/server.py: {e}", exc_info=True)
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

