"""
Error Utilities - Centralized error extraction and handling
"""
from typing import Optional
import logging

logger = logging.getLogger(__name__)


def extract_root_error(error: Exception, max_depth: int = 5) -> Exception:
    """
    Extract the root cause from ExceptionGroup/TaskGroup or nested exceptions.
    
    This function handles:
    - ExceptionGroup (Python 3.11+)
    - TaskGroup exceptions (asyncio)
    - Nested exceptions via __cause__
    
    Args:
        error: The exception to extract root cause from
        max_depth: Maximum depth to traverse (prevents infinite loops)
        
    Returns:
        The root cause exception
    """
    if not error:
        return error
    
    real_error = error
    current_error = error
    depth = 0
    
    # Check if it's an ExceptionGroup (Python 3.11+)
    if hasattr(error, 'exceptions') and len(error.exceptions) > 0:
        # Get the first exception from the group
        real_error = error.exceptions[0]
        current_error = real_error
        logger.debug(f"Extracted error from ExceptionGroup: {type(real_error).__name__}")
        depth += 1
    
    # Traverse nested exceptions (__cause__ or exceptions)
    while depth < max_depth:
        if hasattr(current_error, '__cause__') and current_error.__cause__:
            current_error = current_error.__cause__
            depth += 1
        elif hasattr(current_error, 'exceptions') and len(current_error.exceptions) > 0:
            current_error = current_error.exceptions[0]
            depth += 1
        else:
            break
    
    if current_error != error:
        real_error = current_error
        if depth > 1:
            logger.debug(f"Extracted root error from nested exception (depth {depth}): {type(real_error).__name__}")
    
    return real_error


def get_error_message(error: Exception, max_length: int = 200) -> str:
    """
    Get a clean error message from an exception, handling nested exceptions.
    
    Args:
        error: The exception
        max_length: Maximum length of error message
        
    Returns:
        Clean error message
    """
    root_error = extract_root_error(error)
    error_message = str(root_error)
    
    if len(error_message) > max_length:
        error_message = error_message[:max_length] + "..."
    
    return error_message

