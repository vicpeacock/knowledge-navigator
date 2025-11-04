"""
Test suite for Email Indexer Service
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime

from app.services.email_indexer import EmailIndexer
from app.core.memory_manager import MemoryManager


@pytest.fixture
def mock_memory_manager():
    """Create a mock memory manager"""
    manager = MagicMock(spec=MemoryManager)
    manager.add_long_term_memory = AsyncMock()
    return manager


@pytest.fixture
def email_indexer(mock_memory_manager):
    """Create EmailIndexer instance with mocked dependencies"""
    return EmailIndexer(mock_memory_manager)


@pytest.fixture
def sample_email():
    """Sample email data for testing"""
    return {
        "id": "email123",
        "subject": "Important Meeting Tomorrow",
        "from": "colleague@example.com",
        "to": "user@example.com",
        "date": "2024-01-15T10:00:00Z",
        "snippet": "This is a preview of the email content",
        "body": "This is the full body of the email with important information about the meeting."
    }


@pytest.fixture
def sample_email_no_body():
    """Sample email without body"""
    return {
        "id": "email456",
        "subject": "Simple Email",
        "from": "sender@example.com",
        "date": "2024-01-15T10:00:00Z",
        "snippet": "Just a snippet",
    }


@pytest.mark.asyncio
async def test_should_index_email_with_body(email_indexer, sample_email):
    """Test that emails with body content should be indexed"""
    result = await email_indexer.should_index_email(sample_email)
    assert result is True


@pytest.mark.asyncio
async def test_should_not_index_email_without_body(email_indexer, sample_email_no_body):
    """Test that emails without body and no important keywords should not be indexed"""
    result = await email_indexer.should_index_email(sample_email_no_body)
    assert result is False


@pytest.mark.asyncio
async def test_should_index_email_with_important_keywords(email_indexer, sample_email_no_body):
    """Test that emails with important keywords should be indexed"""
    sample_email_no_body["subject"] = "URGENT: Action Required"
    result = await email_indexer.should_index_email(sample_email_no_body)
    assert result is True


@pytest.mark.asyncio
async def test_build_email_content(email_indexer, sample_email):
    """Test email content building"""
    content = email_indexer._build_email_content(sample_email)
    
    assert "Email from: colleague@example.com" in content
    assert "Subject: Important Meeting Tomorrow" in content
    assert "Body:" in content
    assert sample_email["body"] in content


@pytest.mark.asyncio
async def test_calculate_importance(email_indexer, sample_email):
    """Test importance score calculation"""
    score = await email_indexer._calculate_importance(sample_email)
    
    assert 0.0 <= score <= 1.0
    assert score > 0.5  # Should have decent score with body and important keywords


@pytest.mark.asyncio
async def test_index_email_success(email_indexer, sample_email, mock_memory_manager):
    """Test successful email indexing"""
    session_id = uuid4()
    db = AsyncMock()
    
    result = await email_indexer.index_email(
        db=db,
        email=sample_email,
        session_id=session_id,
    )
    
    assert result is True
    mock_memory_manager.add_long_term_memory.assert_called_once()
    
    # Check call arguments
    call_args = mock_memory_manager.add_long_term_memory.call_args
    assert call_args[1]["learned_from_sessions"] == [session_id]
    assert call_args[1]["importance_score"] > 0.5


@pytest.mark.asyncio
async def test_index_email_skipped(email_indexer, sample_email_no_body, mock_memory_manager):
    """Test that unimportant emails are skipped"""
    session_id = uuid4()
    db = AsyncMock()
    
    result = await email_indexer.index_email(
        db=db,
        email=sample_email_no_body,
        session_id=session_id,
    )
    
    assert result is False
    mock_memory_manager.add_long_term_memory.assert_not_called()


@pytest.mark.asyncio
async def test_index_emails_multiple(email_indexer, sample_email, sample_email_no_body, mock_memory_manager):
    """Test indexing multiple emails"""
    session_id = uuid4()
    db = AsyncMock()
    
    emails = [sample_email, sample_email_no_body]
    result = await email_indexer.index_emails(
        db=db,
        emails=emails,
        session_id=session_id,
    )
    
    assert result["indexed"] == 1
    assert result["skipped"] == 1
    assert result["total"] == 2
    assert len(result["errors"]) == 0


@pytest.mark.asyncio
async def test_index_email_error_handling(email_indexer, sample_email, mock_memory_manager):
    """Test error handling in email indexing"""
    session_id = uuid4()
    db = AsyncMock()
    
    # Make memory manager raise an exception
    mock_memory_manager.add_long_term_memory.side_effect = Exception("Database error")
    
    result = await email_indexer.index_email(
        db=db,
        email=sample_email,
        session_id=session_id,
    )
    
    assert result is False  # Should return False on error


@pytest.mark.asyncio
async def test_index_emails_with_errors(email_indexer, sample_email, mock_memory_manager):
    """Test indexing emails with some errors"""
    session_id = uuid4()
    db = AsyncMock()
    
    # First email fails, second succeeds
    mock_memory_manager.add_long_term_memory.side_effect = [
        Exception("Error 1"),
        None,  # Success for second call
    ]
    
    emails = [sample_email, sample_email]
    result = await email_indexer.index_emails(
        db=db,
        emails=emails,
        session_id=session_id,
    )
    
    assert result["total"] == 2
    assert len(result["errors"]) > 0

