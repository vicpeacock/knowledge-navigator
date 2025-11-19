"""
Test to verify that all LangGraph nodes execute and log activity correctly
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.agents.langgraph_app import (
    build_langgraph_app,
    LangGraphChatState,
)
from app.models.schemas import ChatRequest
from app.core.ollama_client import OllamaClient
from app.core.memory_manager import MemoryManager
from app.services.agent_activity_stream import AgentActivityStream
from app.services.notification_center import NotificationCenter
from app.services.task_queue import TaskQueue


@pytest.fixture
def minimal_state():
    """Create minimal state for testing"""
    session_id = uuid4()
    request = ChatRequest(message="Ciao, come stai?", use_memory=False)
    
    mock_db = AsyncMock()
    mock_ollama = AsyncMock(spec=OllamaClient)
    mock_ollama.generate_with_context = AsyncMock(return_value="Ciao! Sto bene, grazie per aver chiesto.")
    mock_memory = AsyncMock(spec=MemoryManager)
    mock_stream = MagicMock(spec=AgentActivityStream)
    mock_stream.publish = MagicMock()
    
    state: LangGraphChatState = {
        "event": {"role": "user", "content": "Ciao, come stai?"},
        "session_id": session_id,
        "request": request,
        "db": mock_db,
        "ollama": mock_ollama,
        "planner_client": mock_ollama,
        "memory_manager": mock_memory,
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
        "agent_activity_manager": mock_stream,
        "task_queue": TaskQueue(),
        "current_task": None,
        "current_user": None,
    }
    return state


@pytest.mark.asyncio
async def test_all_nodes_execute(minimal_state):
    """Test that all nodes in the graph execute"""
    app = build_langgraph_app()
    
    # Execute graph
    final_state = await app.ainvoke(minimal_state)
    
    # Check agent activity to verify all nodes executed
    agent_activity = final_state.get("agent_activity", [])
    agent_ids = [e.get("agent_id") for e in agent_activity]
    
    # Expected agents that should execute
    expected_agents = [
        "event_handler",
        "orchestrator", 
        "tool_loop",
        "knowledge_agent",
        "notification_collector",
        "response_formatter"
    ]
    
    executed_agents = set(agent_ids)
    
    # Verify each agent executed at least once
    for agent_id in expected_agents:
        assert agent_id in executed_agents, f"Agent {agent_id} did not execute. Executed: {executed_agents}"
    
    # Verify final response exists and is not empty
    assert "chat_response" in final_state
    assert final_state["chat_response"] is not None
    assert final_state["chat_response"].response is not None
    assert len(final_state["chat_response"].response.strip()) > 0
    
    # Verify response was formatted correctly
    chat_response = final_state["chat_response"]
    assert chat_response.session_id == minimal_state["session_id"]
    assert isinstance(chat_response.memory_used, dict)
    assert isinstance(chat_response.tools_used, list)
    assert isinstance(chat_response.agent_activity, list)


@pytest.mark.asyncio
async def test_node_execution_order(minimal_state):
    """Test that nodes execute in the correct order"""
    app = build_langgraph_app()
    
    execution_order = []
    
    # Track execution by monitoring agent_activity
    original_publish = minimal_state["agent_activity_manager"].publish
    
    def track_publish(session_id, event):
        execution_order.append(event.get("agent_id"))
        original_publish(session_id, event)
    
    minimal_state["agent_activity_manager"].publish = track_publish
    
    final_state = await app.ainvoke(minimal_state)
    
    # Expected order: event_handler -> orchestrator -> tool_loop -> knowledge_agent -> notification_collector -> response_formatter
    # Note: Some agents may log multiple times (started/completed), so we check for presence and relative order
    
    assert "event_handler" in execution_order
    assert "orchestrator" in execution_order
    assert "tool_loop" in execution_order
    assert "knowledge_agent" in execution_order
    assert "notification_collector" in execution_order
    assert "response_formatter" in execution_order
    
    # Check relative order (event_handler should come before orchestrator, etc.)
    event_handler_idx = execution_order.index("event_handler")
    orchestrator_idx = execution_order.index("orchestrator")
    tool_loop_idx = execution_order.index("tool_loop")
    response_formatter_idx = execution_order.index("response_formatter")
    
    assert event_handler_idx < orchestrator_idx, "event_handler should execute before orchestrator"
    assert orchestrator_idx < tool_loop_idx, "orchestrator should execute before tool_loop"
    assert tool_loop_idx < response_formatter_idx, "tool_loop should execute before response_formatter"


@pytest.mark.asyncio
async def test_agent_activity_telemetry(minimal_state):
    """Test that agent activity telemetry is published correctly"""
    app = build_langgraph_app()
    
    published_events = []
    
    def track_publish(session_id, event):
        published_events.append(event)
    
    minimal_state["agent_activity_manager"].publish = track_publish
    
    final_state = await app.ainvoke(minimal_state)
    
    # Verify events were published
    assert len(published_events) > 0
    
    # Verify each agent published at least one event
    agent_ids_in_events = set(e.get("agent_id") for e in published_events)
    expected_agents = ["event_handler", "orchestrator", "tool_loop", "knowledge_agent", "notification_collector", "response_formatter"]
    
    for agent_id in expected_agents:
        assert agent_id in agent_ids_in_events, f"Agent {agent_id} did not publish telemetry events"
    
    # Verify events have required fields
    for event in published_events:
        assert "agent_id" in event
        assert "status" in event
        assert "timestamp" in event
        assert event["status"] in ["started", "completed", "waiting", "error"]

