"""
Integration test for chat endpoint - verifies that responses are never empty
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.main import app


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def mock_session_id():
    """Mock session ID"""
    return uuid4()


@pytest.fixture
def mock_user():
    """Mock user"""
    user = MagicMock()
    user.id = uuid4()
    user.email = "test@example.com"
    return user


@pytest.fixture
def mock_tenant_id():
    """Mock tenant ID"""
    return uuid4()


@pytest.mark.asyncio
class TestChatEndpoint:
    """Test chat endpoint to ensure responses are never empty"""
    
    @patch('app.api.sessions.get_db')
    @patch('app.api.sessions.get_current_user')
    @patch('app.api.sessions.get_tenant_id')
    @patch('app.api.sessions.get_ollama_client')
    @patch('app.api.sessions.get_planner_client')
    @patch('app.api.sessions.get_memory_manager')
    @patch('app.api.sessions.get_agent_activity_stream')
    @patch('app.api.sessions.get_background_task_manager')
    @patch('app.api.sessions.get_daily_session_manager')
    async def test_chat_never_returns_empty_response(
        self,
        mock_daily_session_manager,
        mock_background_task_manager,
        mock_agent_activity_stream,
        mock_memory_manager,
        mock_planner_client,
        mock_ollama_client,
        mock_get_tenant_id,
        mock_get_current_user,
        mock_get_db,
        client,
        mock_session_id,
        mock_user,
        mock_tenant_id
    ):
        """Test that chat endpoint never returns an empty response"""
        # Setup mocks
        mock_db = AsyncMock()
        mock_get_db.return_value = mock_db
        mock_get_current_user.return_value = mock_user
        mock_get_tenant_id.return_value = mock_tenant_id
        
        # Mock session
        from app.models.database import Session as SessionModel
        mock_session = MagicMock(spec=SessionModel)
        mock_session.id = mock_session_id
        mock_session.tenant_id = mock_tenant_id
        mock_session.user_id = mock_user.id
        mock_session.status = "active"
        mock_session.session_metadata = {}
        
        # Mock database queries
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_session
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        # Mock Ollama client
        mock_ollama = AsyncMock()
        mock_ollama.generate_with_context = AsyncMock(return_value="Test response from Ollama")
        mock_ollama_client.return_value = mock_ollama
        
        # Mock planner client
        mock_planner = AsyncMock()
        mock_planner_client.return_value = mock_planner
        
        # Mock memory manager
        mock_memory = AsyncMock()
        mock_memory.get_short_term_memory = AsyncMock(return_value=None)
        mock_memory.retrieve_medium_term_memory = AsyncMock(return_value=[])
        mock_memory.retrieve_long_term_memory = AsyncMock(return_value=[])
        mock_memory.retrieve_file_content = AsyncMock(return_value=[])
        mock_memory_manager.return_value = mock_memory
        
        # Mock agent activity stream
        mock_stream = MagicMock()
        mock_stream.publish = MagicMock()
        mock_agent_activity_stream.return_value = mock_stream
        
        # Mock background task manager
        mock_bg_tasks = MagicMock()
        mock_background_task_manager.return_value = mock_bg_tasks
        
        # Mock daily session manager
        mock_daily_mgr = AsyncMock()
        mock_daily_mgr.check_day_transition = AsyncMock(return_value=(False, None))
        mock_daily_session_manager.return_value = mock_daily_mgr
        
        # Mock LangGraph
        with patch('app.api.sessions.run_langgraph_chat') as mock_langgraph:
            from app.models.schemas import ChatResponse
            mock_langgraph.return_value = {
                "chat_response": ChatResponse(
                    response="Test response",
                    session_id=mock_session_id,
                    memory_used={},
                    tools_used=[],
                    tool_details=[],
                    notifications_count=0,
                    high_urgency_notifications=[],
                    agent_activity=[],
                ),
                "plan_metadata": None,
                "assistant_message_saved": False,
            }
            
            # Make request
            response = client.post(
                f"/api/sessions/{mock_session_id}/chat",
                json={"message": "Test message"},
                headers={"Authorization": "Bearer test_token"}
            )
            
            # Assertions
            assert response.status_code == 200
            data = response.json()
            assert "response" in data
            assert data["response"] is not None
            assert len(data["response"].strip()) > 0, "Response should never be empty"
    
    @patch('app.api.sessions.get_db')
    @patch('app.api.sessions.get_current_user')
    @patch('app.api.sessions.get_tenant_id')
    @patch('app.api.sessions.get_ollama_client')
    @patch('app.api.sessions.get_planner_client')
    @patch('app.api.sessions.get_memory_manager')
    @patch('app.api.sessions.get_agent_activity_stream')
    @patch('app.api.sessions.get_background_task_manager')
    @patch('app.api.sessions.get_daily_session_manager')
    async def test_chat_handles_empty_response_from_langgraph(
        self,
        mock_daily_session_manager,
        mock_background_task_manager,
        mock_agent_activity_stream,
        mock_memory_manager,
        mock_planner_client,
        mock_ollama_client,
        mock_get_tenant_id,
        mock_get_current_user,
        mock_get_db,
        client,
        mock_session_id,
        mock_user,
        mock_tenant_id
    ):
        """Test that chat endpoint handles empty response from LangGraph gracefully"""
        # Setup mocks (same as above)
        mock_db = AsyncMock()
        mock_get_db.return_value = mock_db
        mock_get_current_user.return_value = mock_user
        mock_get_tenant_id.return_value = mock_tenant_id
        
        from app.models.database import Session as SessionModel
        mock_session = MagicMock(spec=SessionModel)
        mock_session.id = mock_session_id
        mock_session.tenant_id = mock_tenant_id
        mock_session.user_id = mock_user.id
        mock_session.status = "active"
        mock_session.session_metadata = {}
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_session
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        mock_ollama = AsyncMock()
        mock_ollama_client.return_value = mock_ollama
        mock_planner = AsyncMock()
        mock_planner_client.return_value = mock_planner
        mock_memory = AsyncMock()
        mock_memory.get_short_term_memory = AsyncMock(return_value=None)
        mock_memory.retrieve_medium_term_memory = AsyncMock(return_value=[])
        mock_memory.retrieve_long_term_memory = AsyncMock(return_value=[])
        mock_memory.retrieve_file_content = AsyncMock(return_value=[])
        mock_memory_manager.return_value = mock_memory
        mock_stream = MagicMock()
        mock_agent_activity_stream.return_value = mock_stream
        mock_bg_tasks = MagicMock()
        mock_background_task_manager.return_value = mock_bg_tasks
        mock_daily_mgr = AsyncMock()
        mock_daily_mgr.check_day_transition = AsyncMock(return_value=(False, None))
        mock_daily_session_manager.return_value = mock_daily_mgr
        
        # Mock LangGraph returning empty response
        with patch('app.api.sessions.run_langgraph_chat') as mock_langgraph:
            from app.models.schemas import ChatResponse
            mock_langgraph.return_value = {
                "chat_response": ChatResponse(
                    response="",  # Empty response
                    session_id=mock_session_id,
                    memory_used={},
                    tools_used=[],
                    tool_details=[],
                    notifications_count=0,
                    high_urgency_notifications=[],
                    agent_activity=[],
                ),
                "plan_metadata": None,
                "assistant_message_saved": False,
            }
            
            # Make request
            response = client.post(
                f"/api/sessions/{mock_session_id}/chat",
                json={"message": "Test message"},
                headers={"Authorization": "Bearer test_token"}
            )
            
            # Assertions - should still return a non-empty response due to fallback
            assert response.status_code == 200
            data = response.json()
            assert "response" in data
            assert data["response"] is not None
            assert len(data["response"].strip()) > 0, "Response should have fallback message when LangGraph returns empty"

