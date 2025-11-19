"""
Complete integration test for LangGraph - verifies all nodes execute correctly
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime, timezone

from app.agents.langgraph_app import (
    build_langgraph_app,
    event_handler_node,
    orchestrator_node,
    tool_loop_node,
    knowledge_agent_node,
    notification_collector_node,
    response_formatter_node,
    LangGraphChatState,
)
from app.models.schemas import ChatRequest
from app.core.ollama_client import OllamaClient
from app.core.memory_manager import MemoryManager
from app.services.agent_activity_stream import AgentActivityStream
from app.services.notification_center import NotificationCenter
from app.services.task_queue import TaskQueue


@pytest.fixture
def mock_db():
    """Mock database session"""
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
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
    return memory


@pytest.fixture
def mock_agent_activity_stream():
    """Mock agent activity stream"""
    stream = MagicMock(spec=AgentActivityStream)
    stream.publish = MagicMock()
    return stream


@pytest.fixture
def base_state(mock_db, mock_ollama, mock_memory_manager, mock_agent_activity_stream):
    """Create base state for testing"""
    session_id = uuid4()
    request = ChatRequest(message="Test message", use_memory=True)
    
    state: LangGraphChatState = {
        "event": {"role": "user", "content": "Test message"},
        "session_id": session_id,
        "request": request,
        "db": mock_db,
        "ollama": mock_ollama,
        "planner_client": mock_ollama,
        "memory_manager": mock_memory_manager,
        "session_context": [],
        "retrieved_memory": [],
        "memory_used": {},
        "messages": [],
        "tool_calls": [],
        "tool_results": [],
        "notifications": [],
        "high_urgency_notifications": [],
        "notification_center": NotificationCenter(),
        "previous_messages": [],
        "acknowledgement": False,
        "plan": [],
        "plan_index": 0,
        "plan_dirty": False,
        "plan_completed": True,
        "plan_origin": None,
        "routing_decision": "",
        "response": None,
        "chat_response": None,
        "assistant_message_saved": False,
        "done": False,
        "agent_activity": [],
        "agent_activity_manager": mock_agent_activity_stream,
        "task_queue": TaskQueue(),
        "current_task": None,
        "current_user": None,
    }
    return state


@pytest.mark.asyncio
class TestLangGraphNodes:
    """Test individual LangGraph nodes"""
    
    async def test_event_handler_node(self, base_state):
        """Test event_handler_node executes correctly"""
        result_state = await event_handler_node(base_state)
        
        assert "messages" in result_state
        assert len(result_state["messages"]) == 1
        assert result_state["messages"][0]["role"] == "user"
        assert result_state["messages"][0]["content"] == "Test message"
        
        # Check agent activity was logged
        agent_activity = result_state.get("agent_activity", [])
        event_handler_events = [e for e in agent_activity if e.get("agent_id") == "event_handler"]
        assert len(event_handler_events) >= 1
        assert event_handler_events[-1]["status"] == "completed"
    
    async def test_orchestrator_node(self, base_state):
        """Test orchestrator_node executes correctly"""
        result_state = await orchestrator_node(base_state)
        
        # Check routing decision was set
        assert "routing_decision" in result_state or "_routing_target" in result_state
        
        # Check agent activity was logged
        agent_activity = result_state.get("agent_activity", [])
        orchestrator_events = [e for e in agent_activity if e.get("agent_id") == "orchestrator"]
        assert len(orchestrator_events) >= 1
        assert orchestrator_events[-1]["status"] == "completed"
    
    async def test_tool_loop_node_no_tools(self, base_state, mock_ollama):
        """Test tool_loop_node when no tools are needed"""
        # Mock Ollama to return a simple response without tool calls
        mock_ollama.generate_with_context = AsyncMock(return_value="Simple response without tools")
        
        result_state = await tool_loop_node(base_state)
        
        # Check response was set
        assert "response" in result_state
        assert result_state["response"] is not None
        assert len(result_state["response"].strip()) > 0
        
        # Check agent activity was logged
        agent_activity = result_state.get("agent_activity", [])
        tool_loop_events = [e for e in agent_activity if e.get("agent_id") == "tool_loop"]
        assert len(tool_loop_events) >= 1
        assert tool_loop_events[-1]["status"] == "completed"
    
    async def test_knowledge_agent_node(self, base_state):
        """Test knowledge_agent_node executes correctly"""
        # Set response so knowledge_agent has something to work with
        base_state["response"] = "Test assistant response"
        base_state["previous_messages"] = [
            {"role": "user", "content": "Previous message"},
            {"role": "assistant", "content": "Previous response"},
        ]
        
        result_state = await knowledge_agent_node(base_state)
        
        # Check agent activity was logged
        agent_activity = result_state.get("agent_activity", [])
        knowledge_events = [e for e in agent_activity if e.get("agent_id") == "knowledge_agent"]
        assert len(knowledge_events) >= 1
        assert knowledge_events[-1]["status"] == "completed"
    
    async def test_notification_collector_node(self, base_state):
        """Test notification_collector_node executes correctly"""
        result_state = await notification_collector_node(base_state)
        
        # Check notifications were snapshotted
        assert "notifications" in result_state
        
        # Check agent activity was logged
        agent_activity = result_state.get("agent_activity", [])
        notification_events = [e for e in agent_activity if e.get("agent_id") == "notification_collector"]
        assert len(notification_events) >= 1
        assert notification_events[-1]["status"] == "completed"
    
    async def test_response_formatter_node(self, base_state):
        """Test response_formatter_node executes correctly"""
        # Set response so formatter has something to format
        base_state["response"] = "Test response"
        base_state["tools_used"] = []
        base_state["tool_results"] = []
        
        result_state = await response_formatter_node(base_state)
        
        # Check chat_response was created
        assert "chat_response" in result_state
        assert result_state["chat_response"] is not None
        assert result_state["chat_response"].response is not None
        assert len(result_state["chat_response"].response.strip()) > 0
        
        # Check agent activity was logged
        agent_activity = result_state.get("agent_activity", [])
        formatter_events = [e for e in agent_activity if e.get("agent_id") == "response_formatter"]
        assert len(formatter_events) >= 1
        assert formatter_events[-1]["status"] == "completed"


@pytest.mark.asyncio
class TestLangGraphFullExecution:
    """Test complete LangGraph execution"""
    
    async def test_full_graph_execution(self, base_state, mock_ollama):
        """Test that the full graph executes all nodes"""
        # Mock Ollama to return a simple response
        mock_ollama.generate_with_context = AsyncMock(return_value="Complete test response")
        
        # Build and compile graph
        app = build_langgraph_app()
        
        # Execute graph
        final_state = await app.ainvoke(base_state)
        
        # Verify all nodes executed
        agent_activity = final_state.get("agent_activity", [])
        agent_ids = [e.get("agent_id") for e in agent_activity]
        
        # Check that all expected agents executed
        expected_agents = ["event_handler", "orchestrator", "tool_loop", "knowledge_agent", "notification_collector", "response_formatter"]
        executed_agents = set(agent_ids)
        
        for agent_id in expected_agents:
            assert agent_id in executed_agents, f"Agent {agent_id} did not execute. Executed agents: {executed_agents}"
        
        # Verify final response exists
        assert "chat_response" in final_state
        assert final_state["chat_response"] is not None
        assert final_state["chat_response"].response is not None
        assert len(final_state["chat_response"].response.strip()) > 0
    
    async def test_graph_handles_empty_response(self, base_state, mock_ollama):
        """Test that graph handles empty responses gracefully"""
        # Mock Ollama to return empty response
        mock_ollama.generate_with_context = AsyncMock(return_value="")
        
        app = build_langgraph_app()
        final_state = await app.ainvoke(base_state)
        
        # Should still have a valid response due to fallbacks
        assert "chat_response" in final_state
        assert final_state["chat_response"] is not None
        assert final_state["chat_response"].response is not None
        assert len(final_state["chat_response"].response.strip()) > 0
    
    async def test_graph_with_tool_calls(self, base_state, mock_ollama):
        """Test graph execution when tools are called"""
        from app.core.tool_manager import ToolManager
        
        # Mock tool execution
        mock_tool_manager = AsyncMock(spec=ToolManager)
        mock_tool_manager.get_available_tools = AsyncMock(return_value=[])
        mock_tool_manager.execute_tool = AsyncMock(return_value={"result": "Tool executed successfully"})
        
        # Mock Ollama to return tool calls
        mock_ollama.generate_with_context = AsyncMock(
            return_value={
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
            }
        )
        
        # Patch ToolManager in tool_loop_node
        with patch('app.agents.langgraph_app.ToolManager', return_value=mock_tool_manager):
            app = build_langgraph_app()
            final_state = await app.ainvoke(base_state)
            
            # Should have executed tools and generated response
            assert "chat_response" in final_state
            assert final_state["chat_response"] is not None
            assert final_state["chat_response"].response is not None

