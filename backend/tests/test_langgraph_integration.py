"""
Complete integration test for LangGraph - tests the full flow from request to response
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.agents.langgraph_app import run_langgraph_chat
from app.models.schemas import ChatRequest
from app.core.ollama_client import OllamaClient
from app.core.memory_manager import MemoryManager
from app.services.agent_activity_stream import AgentActivityStream


@pytest.fixture
def mock_db():
    """Mock database session"""
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    
    # Mock session query
    mock_session = MagicMock()
    mock_session.id = uuid4()
    mock_session.tenant_id = uuid4()
    mock_session.user_id = uuid4()
    mock_session.status = "active"
    mock_session.session_metadata = {}
    
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_session
    mock_result.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=mock_result)
    
    return db


@pytest.fixture
def mock_ollama():
    """Mock Ollama client"""
    ollama = AsyncMock(spec=OllamaClient)
    ollama.generate_with_context = AsyncMock(return_value="Test response from Ollama")
    return ollama


@pytest.fixture
def mock_memory_manager():
    """Mock memory manager"""
    memory = AsyncMock(spec=MemoryManager)
    memory.get_short_term_memory = AsyncMock(return_value=None)
    memory.retrieve_medium_term_memory = AsyncMock(return_value=[])
    memory.retrieve_long_term_memory = AsyncMock(return_value=[])
    memory.retrieve_file_content = AsyncMock(return_value=[])
    memory.update_short_term_memory = AsyncMock()
    return memory


@pytest.fixture
def mock_agent_activity_stream():
    """Mock agent activity stream"""
    stream = MagicMock(spec=AgentActivityStream)
    stream.publish = MagicMock()
    return stream


@pytest.mark.asyncio
async def test_run_langgraph_chat_complete_flow(
    mock_db,
    mock_ollama,
    mock_memory_manager,
    mock_agent_activity_stream
):
    """Test complete LangGraph execution flow"""
    session_id = uuid4()
    request = ChatRequest(message="Ciao, come stai?", use_memory=False)
    
    result = await run_langgraph_chat(
        db=mock_db,
        session_id=session_id,
        request=request,
        ollama=mock_ollama,
        planner_client=mock_ollama,
        agent_activity_stream=mock_agent_activity_stream,
        memory_manager=mock_memory_manager,
        session_context=[],
        retrieved_memory=[],
        memory_used={},
        previous_messages=None,
        pending_plan=None,
        current_user=None,
    )
    
    # Verify result structure
    assert "chat_response" in result
    assert result["chat_response"] is not None
    assert result["chat_response"].response is not None
    assert len(result["chat_response"].response.strip()) > 0
    
    # Verify response content
    chat_response = result["chat_response"]
    assert chat_response.session_id == session_id
    assert isinstance(chat_response.memory_used, dict)
    assert isinstance(chat_response.tools_used, list)
    assert isinstance(chat_response.agent_activity, list)
    
    # Verify agent activity was logged
    assert len(chat_response.agent_activity) > 0
    agent_ids = [e.get("agent_id") for e in chat_response.agent_activity]
    expected_agents = ["event_handler", "orchestrator", "tool_loop", "knowledge_agent", "notification_collector", "response_formatter"]
    
    for agent_id in expected_agents:
        assert agent_id in agent_ids, f"Agent {agent_id} did not log activity"


@pytest.mark.asyncio
async def test_run_langgraph_chat_with_empty_response_from_ollama(
    mock_db,
    mock_ollama,
    mock_memory_manager,
    mock_agent_activity_stream
):
    """Test that LangGraph handles empty response from Ollama gracefully"""
    session_id = uuid4()
    request = ChatRequest(message="Test", use_memory=False)
    
    # Mock Ollama to return empty response
    mock_ollama.generate_with_context = AsyncMock(return_value="")
    
    result = await run_langgraph_chat(
        db=mock_db,
        session_id=session_id,
        request=request,
        ollama=mock_ollama,
        planner_client=mock_ollama,
        agent_activity_stream=mock_agent_activity_stream,
        memory_manager=mock_memory_manager,
        session_context=[],
        retrieved_memory=[],
        memory_used={},
        previous_messages=None,
        pending_plan=None,
        current_user=None,
    )
    
    # Should still have a valid response due to fallbacks
    assert "chat_response" in result
    assert result["chat_response"] is not None
    assert result["chat_response"].response is not None
    assert len(result["chat_response"].response.strip()) > 0


@pytest.mark.asyncio
async def test_run_langgraph_chat_with_tool_calls(
    mock_db,
    mock_ollama,
    mock_memory_manager,
    mock_agent_activity_stream
):
    """Test LangGraph execution when tools are called"""
    session_id = uuid4()
    request = ChatRequest(message="Ci sono email non lette?", use_memory=False)
    
    # Mock Ollama to return tool calls
    mock_ollama.generate_with_context = AsyncMock(
        side_effect=[
            # First call: returns tool calls
            {
                "content": "",
                "raw_result": {
                    "message": {
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "get_emails",
                                    "arguments": '{"query": "is:unread"}'
                                }
                            }
                        ]
                    }
                },
                "_raw_tool_calls": [
                    {
                        "function": {
                            "name": "get_emails",
                            "arguments": {"query": "is:unread"}
                        }
                    }
                ]
            },
            # Second call: final response after tool execution
            "Ho controllato le tue email. Non ci sono email non lette."
        ]
    )
    
    # Mock tool execution
    with patch('app.agents.langgraph_app.ToolManager') as mock_tool_manager_class:
        mock_tool_manager = AsyncMock()
        mock_tool_manager.get_available_tools = AsyncMock(return_value=[])
        mock_tool_manager.execute_tool = AsyncMock(return_value={
            "count": 0,
            "emails": []
        })
        mock_tool_manager_class.return_value = mock_tool_manager
        
        result = await run_langgraph_chat(
            db=mock_db,
            session_id=session_id,
            request=request,
            ollama=mock_ollama,
            planner_client=mock_ollama,
            agent_activity_stream=mock_agent_activity_stream,
            memory_manager=mock_memory_manager,
            session_context=[],
            retrieved_memory=[],
            memory_used={},
            previous_messages=None,
            pending_plan=None,
            current_user=None,
        )
        
        # Verify result
        assert "chat_response" in result
        assert result["chat_response"] is not None
        assert result["chat_response"].response is not None
        assert len(result["chat_response"].response.strip()) > 0

