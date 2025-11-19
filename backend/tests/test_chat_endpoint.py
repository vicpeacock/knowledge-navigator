"""
Integration test for chat endpoint - verifies that responses are never empty
FIXED VERSION with proper dependency overrides
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.main import app
from app.api.sessions import get_db, get_current_user, get_tenant_id
from app.core.dependencies import (
    get_ollama_client,
    get_planner_client,
    get_memory_manager,
    get_agent_activity_stream,
    get_background_task_manager,
    get_daily_session_manager,
)


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
    user.timezone = "UTC"  # Required for daily_session_manager
    return user


@pytest.fixture
def mock_tenant_id():
    """Mock tenant ID"""
    return uuid4()


@pytest.fixture
def client():
    """Create test client"""
    # Clear any existing overrides
    app.dependency_overrides.clear()
    return TestClient(app)


@pytest.mark.asyncio
class TestChatEndpoint:
    """Test chat endpoint to ensure responses are never empty"""
    
    async def test_chat_never_returns_empty_response(
        self,
        client,
        mock_session_id,
        mock_user,
        mock_tenant_id
    ):
        """Test that chat endpoint never returns an empty response"""
        # Setup mocks
        mock_db = AsyncMock()
        
        # Mock session
        from app.models.database import Session as SessionModel
        mock_session = MagicMock(spec=SessionModel)
        mock_session.id = mock_session_id
        mock_session.tenant_id = mock_tenant_id
        mock_session.user_id = mock_user.id
        mock_session.status = "active"
        mock_session.session_metadata = {}
        
        # Mock database queries
        # Need to handle multiple queries: session query and user query (for daily_session_manager)
        from app.models.database import User as UserModel
        
        def mock_execute(query):
            mock_result = MagicMock()
            # Check if query is for User (daily_session_manager needs user with timezone)
            if hasattr(query, 'column_descriptions') or str(query).find('user') != -1 or str(query).find('User') != -1:
                # Return mock user for daily_session_manager
                mock_user_db = MagicMock(spec=UserModel)
                mock_user_db.id = mock_user.id
                mock_user_db.tenant_id = mock_tenant_id
                mock_user_db.timezone = "UTC"
                mock_result.scalar_one_or_none.return_value = mock_user_db
            else:
                # Return mock session for session query
                mock_result.scalar_one_or_none.return_value = mock_session
                mock_result.scalars.return_value.all.return_value = []
            return mock_result
        
        mock_db.execute = AsyncMock(side_effect=mock_execute)
        
        # Mock Ollama client
        mock_ollama = AsyncMock()
        mock_ollama.generate_with_context = AsyncMock(return_value="Test response from Ollama")
        
        # Mock planner client
        mock_planner = AsyncMock()
        
        # Mock memory manager
        mock_memory = AsyncMock()
        mock_memory.get_short_term_memory = AsyncMock(return_value=None)
        mock_memory.retrieve_medium_term_memory = AsyncMock(return_value=[])
        mock_memory.retrieve_long_term_memory = AsyncMock(return_value=[])
        mock_memory.retrieve_file_content = AsyncMock(return_value=[])
        
        # Mock agent activity stream
        mock_stream = MagicMock()
        mock_stream.publish = MagicMock()
        
        # Mock background task manager
        mock_bg_tasks = MagicMock()
        
        # Mock daily session manager
        mock_daily_mgr = AsyncMock()
        mock_daily_mgr.check_day_transition = AsyncMock(return_value=(False, None))
        
        # Override dependencies
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_tenant_id] = lambda: mock_tenant_id
        app.dependency_overrides[get_ollama_client] = lambda: mock_ollama
        app.dependency_overrides[get_planner_client] = lambda: mock_planner
        app.dependency_overrides[get_memory_manager] = lambda: mock_memory
        app.dependency_overrides[get_agent_activity_stream] = lambda: mock_stream
        app.dependency_overrides[get_background_task_manager] = lambda: mock_bg_tasks
        app.dependency_overrides[get_daily_session_manager] = lambda db: mock_daily_mgr
        
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
            
            try:
                # Make request
                response = client.post(
                    f"/api/sessions/{mock_session_id}/chat",
                    json={"message": "Test message", "session_id": str(mock_session_id)},
                    headers={"Authorization": "Bearer test_token"}
                )
                
                # Assertions
                assert response.status_code == 200
                data = response.json()
                assert "response" in data
                assert data["response"] is not None
                # Day transition responses can be empty (frontend shows dialog)
                if data.get("day_transition_pending"):
                    assert data.get("new_session_id") is not None, "Day transition should include new_session_id"
                else:
                    assert len(data["response"].strip()) > 0, "Response should never be empty (unless day transition)"
            finally:
                # Clean up dependency overrides
                app.dependency_overrides.clear()
    
    async def test_chat_handles_empty_response_from_langgraph(
        self,
        client,
        mock_session_id,
        mock_user,
        mock_tenant_id
    ):
        """Test that chat endpoint handles empty response from LangGraph gracefully"""
        # Setup mocks (same as above)
        mock_db = AsyncMock()
        
        from app.models.database import Session as SessionModel, User as UserModel
        mock_session = MagicMock(spec=SessionModel)
        mock_session.id = mock_session_id
        mock_session.tenant_id = mock_tenant_id
        mock_session.user_id = mock_user.id
        mock_session.status = "active"
        mock_session.session_metadata = {}
        
        # Mock database queries - need to handle both session and user queries
        def mock_execute(query):
            mock_result = MagicMock()
            # Check if query is for User (daily_session_manager needs user with timezone)
            query_str = str(query).lower()
            if 'user' in query_str and ('timezone' in query_str or 'select' in query_str):
                # Return mock user for daily_session_manager
                mock_user_db = MagicMock(spec=UserModel)
                mock_user_db.id = mock_user.id
                mock_user_db.tenant_id = mock_tenant_id
                mock_user_db.timezone = "UTC"
                mock_result.scalar_one_or_none.return_value = mock_user_db
            else:
                # Return mock session for session query
                mock_result.scalar_one_or_none.return_value = mock_session
                mock_result.scalars.return_value.all.return_value = []
            return mock_result
        
        mock_db.execute = AsyncMock(side_effect=mock_execute)
        
        mock_ollama = AsyncMock()
        mock_planner = AsyncMock()
        mock_memory = AsyncMock()
        mock_memory.get_short_term_memory = AsyncMock(return_value=None)
        mock_memory.retrieve_medium_term_memory = AsyncMock(return_value=[])
        mock_memory.retrieve_long_term_memory = AsyncMock(return_value=[])
        mock_memory.retrieve_file_content = AsyncMock(return_value=[])
        mock_stream = MagicMock()
        mock_bg_tasks = MagicMock()
        mock_daily_mgr = AsyncMock()
        mock_daily_mgr.check_day_transition = AsyncMock(return_value=(False, None))
        
        # Override dependencies
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_tenant_id] = lambda: mock_tenant_id
        app.dependency_overrides[get_ollama_client] = lambda: mock_ollama
        app.dependency_overrides[get_planner_client] = lambda: mock_planner
        app.dependency_overrides[get_memory_manager] = lambda: mock_memory
        app.dependency_overrides[get_agent_activity_stream] = lambda: mock_stream
        app.dependency_overrides[get_background_task_manager] = lambda: mock_bg_tasks
        app.dependency_overrides[get_daily_session_manager] = lambda db: mock_daily_mgr
        
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
            
            try:
                # Make request
                response = client.post(
                    f"/api/sessions/{mock_session_id}/chat",
                    json={"message": "Test message", "session_id": str(mock_session_id)},
                    headers={"Authorization": "Bearer test_token"}
                )
                
                # Assertions - should still return a non-empty response due to fallback
                assert response.status_code == 200
                data = response.json()
                assert "response" in data
                assert data["response"] is not None
                # Day transition responses can be empty (frontend shows dialog)
                if data.get("day_transition_pending"):
                    assert data.get("new_session_id") is not None, "Day transition should include new_session_id"
                else:
                    assert len(data["response"].strip()) > 0, "Response should have fallback message when LangGraph returns empty"
            finally:
                # Clean up dependency overrides
                app.dependency_overrides.clear()

