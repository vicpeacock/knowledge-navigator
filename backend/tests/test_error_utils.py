"""
Unit tests for error utilities
"""
import pytest
from app.core.error_utils import extract_root_error, get_error_message


class TestExtractRootError:
    """Test root error extraction"""
    
    def test_simple_error(self):
        """Test extraction from simple error"""
        error = ValueError("Simple error")
        assert extract_root_error(error) == error
    
    def test_nested_error(self):
        """Test extraction from nested error"""
        inner_error = ValueError("Inner error")
        outer_error = RuntimeError("Outer error")
        outer_error.__cause__ = inner_error
        
        extracted = extract_root_error(outer_error)
        assert extracted == inner_error
    
    def test_exception_group(self):
        """Test extraction from ExceptionGroup (Python 3.11+)"""
        try:
            raise ValueError("First error")
        except ValueError as e1:
            try:
                raise RuntimeError("Second error") from e1
            except RuntimeError as e2:
                # Simulate ExceptionGroup behavior
                class MockExceptionGroup(Exception):
                    def __init__(self, exceptions):
                        self.exceptions = exceptions
                        super().__init__("ExceptionGroup")
                
                group = MockExceptionGroup([e1, e2])
                extracted = extract_root_error(group)
                # Should extract first exception
                assert isinstance(extracted, ValueError)
    
    def test_deeply_nested_error(self):
        """Test extraction from deeply nested error"""
        error1 = ValueError("Level 1")
        error2 = RuntimeError("Level 2")
        error3 = TypeError("Level 3")
        
        error2.__cause__ = error1
        error3.__cause__ = error2
        
        extracted = extract_root_error(error3)
        assert extracted == error1  # Should get to root


class TestGetErrorMessage:
    """Test error message extraction"""
    
    def test_simple_error_message(self):
        """Test message from simple error"""
        error = ValueError("Simple error message")
        message = get_error_message(error)
        assert "Simple error message" in message
    
    def test_nested_error_message(self):
        """Test message from nested error"""
        inner_error = ValueError("Inner message")
        outer_error = RuntimeError("Outer message")
        outer_error.__cause__ = inner_error
        
        message = get_error_message(outer_error)
        assert "Inner message" in message
    
    def test_message_truncation(self):
        """Test message truncation"""
        long_message = "A" * 300
        error = ValueError(long_message)
        message = get_error_message(error, max_length=200)
        assert len(message) <= 203  # 200 + "..."
        assert message.endswith("...")

