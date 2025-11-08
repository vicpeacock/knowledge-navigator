"""
Test suite for Web Content Indexer Service
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.services.web_indexer import WebIndexer
from app.core.memory_manager import MemoryManager


@pytest.fixture
def mock_memory_manager():
    """Create a mock memory manager"""
    manager = MagicMock(spec=MemoryManager)
    manager.add_long_term_memory = AsyncMock()
    return manager


@pytest.fixture
def web_indexer(mock_memory_manager):
    """Create WebIndexer instance with mocked dependencies"""
    return WebIndexer(mock_memory_manager)


@pytest.fixture
def sample_search_results():
    """Sample web search results"""
    return [
        {
            "title": "Test Article 1",
            "url": "https://example.com/article1",
            "content": "This is the content of article 1 with important information."
        },
        {
            "title": "Test Article 2",
            "url": "https://example.com/article2",
            "content": "This is the content of article 2."
        },
    ]


@pytest.fixture
def sample_snapshot():
    """Sample browser snapshot content"""
    return """
text: "Welcome to our website"
value: "Click here"
aria-label: "Navigation menu"
name: "search"
    """


@pytest.mark.asyncio
async def test_extract_text_from_snapshot(web_indexer, sample_snapshot):
    """Test text extraction from browser snapshot"""
    text = web_indexer.extract_text_from_snapshot(sample_snapshot)
    
    assert "Welcome to our website" in text
    assert "Click here" in text
    assert "Navigation menu" in text


@pytest.mark.asyncio
async def test_index_web_search_results(web_indexer, sample_search_results, mock_memory_manager):
    """Test indexing web search results"""
    session_id = uuid4()
    db = AsyncMock()
    search_query = "test query"
    
    result = await web_indexer.index_web_search_results(
        db=db,
        search_query=search_query,
        results=sample_search_results,
        session_id=session_id,
    )
    
    assert result["indexed"] == 2
    assert result["total"] == 2
    assert len(result["errors"]) == 0
    
    # Verify memory manager was called
    assert mock_memory_manager.add_long_term_memory.call_count == 2


@pytest.mark.asyncio
async def test_index_web_search_results_limit(web_indexer, mock_memory_manager):
    """Test that indexing is limited to top 5 results"""
    session_id = uuid4()
    db = AsyncMock()
    
    # Create 10 results
    results = [
        {"title": f"Article {i}", "url": f"https://example.com/{i}", "content": f"Content {i}"}
        for i in range(10)
    ]
    
    result = await web_indexer.index_web_search_results(
        db=db,
        search_query="test",
        results=results,
        session_id=session_id,
    )
    
    # Should only index top 5
    assert result["indexed"] == 5
    assert mock_memory_manager.add_long_term_memory.call_count == 5


@pytest.mark.asyncio
async def test_index_web_fetch_result(web_indexer, mock_memory_manager):
    """Test indexing web fetch result"""
    session_id = uuid4()
    db = AsyncMock()
    url = "https://example.com/page"
    
    fetch_result = {
        "title": "Test Page",
        "content": "This is the page content with useful information.",
        "links": ["https://example.com/link1", "https://example.com/link2"],
    }
    
    result = await web_indexer.index_web_fetch_result(
        db=db,
        url=url,
        result=fetch_result,
        session_id=session_id,
    )
    
    assert result is True
    mock_memory_manager.add_long_term_memory.assert_called_once()
    
    # Check call arguments
    call_args = mock_memory_manager.add_long_term_memory.call_args
    assert call_args[1]["learned_from_sessions"] == [session_id]
    assert "Test Page" in call_args[1]["content"]


@pytest.mark.asyncio
async def test_index_web_fetch_result_no_content(web_indexer, mock_memory_manager):
    """Test that web fetch results without content are not indexed"""
    session_id = uuid4()
    db = AsyncMock()
    
    fetch_result = {
        "title": "Test Page",
        "content": "",  # Empty content
        "links": [],
    }
    
    result = await web_indexer.index_web_fetch_result(
        db=db,
        url="https://example.com/page",
        result=fetch_result,
        session_id=session_id,
    )
    
    assert result is False
    mock_memory_manager.add_long_term_memory.assert_not_called()


@pytest.mark.asyncio
async def test_index_browser_snapshot(web_indexer, sample_snapshot, mock_memory_manager):
    """Test indexing browser snapshot"""
    session_id = uuid4()
    db = AsyncMock()
    url = "https://example.com"
    
    result = await web_indexer.index_browser_snapshot(
        db=db,
        url=url,
        snapshot=sample_snapshot,
        session_id=session_id,
    )
    
    assert result is True
    mock_memory_manager.add_long_term_memory.assert_called_once()


@pytest.mark.asyncio
async def test_index_browser_snapshot_insufficient_content(web_indexer, mock_memory_manager):
    """Test that snapshots with insufficient content are not indexed"""
    session_id = uuid4()
    db = AsyncMock()
    
    # Very short snapshot
    short_snapshot = "x" * 10
    
    result = await web_indexer.index_browser_snapshot(
        db=db,
        url="https://example.com",
        snapshot=short_snapshot,
        session_id=session_id,
    )
    
    assert result is False
    mock_memory_manager.add_long_term_memory.assert_not_called()


@pytest.mark.asyncio
async def test_index_web_search_results_error_handling(web_indexer, sample_search_results, mock_memory_manager):
    """Test error handling in web search results indexing"""
    session_id = uuid4()
    db = AsyncMock()
    
    # Make memory manager raise exception on second call
    mock_memory_manager.add_long_term_memory.side_effect = [
        None,  # First succeeds
        Exception("Database error"),  # Second fails
    ]
    
    result = await web_indexer.index_web_search_results(
        db=db,
        search_query="test",
        results=sample_search_results,
        session_id=session_id,
    )
    
    assert result["indexed"] == 1
    assert len(result["errors"]) == 1


@pytest.mark.asyncio
async def test_index_web_fetch_result_error_handling(web_indexer, mock_memory_manager):
    """Test error handling in web fetch indexing"""
    session_id = uuid4()
    db = AsyncMock()
    
    mock_memory_manager.add_long_term_memory.side_effect = Exception("Database error")
    
    fetch_result = {
        "title": "Test Page",
        "content": "Content here",
        "links": [],
    }
    
    result = await web_indexer.index_web_fetch_result(
        db=db,
        url="https://example.com",
        result=fetch_result,
        session_id=session_id,
    )
    
    assert result is False

