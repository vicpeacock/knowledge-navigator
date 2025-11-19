#!/usr/bin/env python3
"""
Debug script to test LangGraph execution and verify all nodes execute
"""
import asyncio
import sys
import os
from uuid import uuid4

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.agents.langgraph_app import build_langgraph_app, LangGraphChatState
from app.models.schemas import ChatRequest
from app.core.ollama_client import OllamaClient
from app.core.memory_manager import MemoryManager
from app.services.agent_activity_stream import AgentActivityStream
from app.services.notification_center import NotificationCenter
from app.services.task_queue import TaskQueue
from app.core.dependencies import get_task_queue


async def test_langgraph_execution():
    """Test LangGraph execution with minimal mocks"""
    print("🔨 Building LangGraph application...")
    app = build_langgraph_app()
    print("✅ LangGraph application built")
    
    # Create minimal state
    session_id = uuid4()
    request = ChatRequest(message="Ciao, come stai?", use_memory=False)
    
    # Mock dependencies
    mock_db = type('MockDB', (), {
        'execute': lambda *args, **kwargs: type('Result', (), {
            'scalar_one_or_none': lambda: type('Session', (), {
                'id': session_id,
                'tenant_id': uuid4(),
                'user_id': uuid4(),
                'status': 'active',
                'session_metadata': {}
            })(),
            'scalars': lambda: type('Scalars', (), {
                'all': lambda: []
            })()
        })()
    })()
    
    mock_ollama = type('MockOllama', (), {
        'generate_with_context': lambda *args, **kwargs: "Ciao! Sto bene, grazie per aver chiesto."
    })()
    
    mock_memory = type('MockMemory', (), {
        'get_short_term_memory': lambda *args, **kwargs: None,
        'retrieve_medium_term_memory': lambda *args, **kwargs: [],
        'retrieve_long_term_memory': lambda *args, **kwargs: [],
        'retrieve_file_content': lambda *args, **kwargs: [],
        'update_short_term_memory': lambda *args, **kwargs: None
    })()
    
    mock_stream = type('MockStream', (), {
        'publish': lambda *args, **kwargs: None
    })()
    
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
    
    print(f"\n🚀 Executing LangGraph with session {session_id}...")
    print(f"   Request: {request.message}")
    
    try:
        final_state = await app.ainvoke(state)
        print("\n✅ LangGraph execution completed successfully")
        
        # Check agent activity
        agent_activity = final_state.get("agent_activity", [])
        print(f"\n📊 Agent Activity: {len(agent_activity)} events")
        
        agent_ids = [e.get("agent_id") for e in agent_activity]
        unique_agents = set(agent_ids)
        print(f"   Unique agents: {unique_agents}")
        
        expected_agents = ["event_handler", "orchestrator", "tool_loop", "knowledge_agent", "notification_collector", "response_formatter"]
        missing_agents = [a for a in expected_agents if a not in unique_agents]
        
        if missing_agents:
            print(f"\n❌ Missing agents: {missing_agents}")
        else:
            print(f"\n✅ All expected agents executed")
        
        # Check response
        if "chat_response" not in final_state:
            print("\n❌ CRITICAL: chat_response missing from final_state!")
            print(f"   Final state keys: {list(final_state.keys())}")
            return False
        
        chat_response = final_state["chat_response"]
        if not chat_response:
            print("\n❌ CRITICAL: chat_response is None!")
            return False
        
        if not chat_response.response or not chat_response.response.strip():
            print("\n❌ CRITICAL: chat_response.response is empty!")
            print(f"   Response length: {len(chat_response.response) if chat_response.response else 0}")
            return False
        
        print(f"\n✅ Response generated successfully")
        print(f"   Response length: {len(chat_response.response)} characters")
        print(f"   Response preview: {chat_response.response[:100]}...")
        
        return True
        
    except Exception as e:
        print(f"\n❌ LangGraph execution failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    result = asyncio.run(test_langgraph_execution())
    sys.exit(0 if result else 1)

