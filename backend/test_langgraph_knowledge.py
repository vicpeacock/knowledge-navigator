from __future__ import annotations

import asyncio
from typing import Any, Dict, List
from uuid import uuid4

import pytest

from app.agents import langgraph_app
from app.models.schemas import ChatRequest, ChatResponse


class DummyMemoryManager:
    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    async def update_short_term_memory(self, db: Any, session_id: Any, context: Dict[str, Any]) -> None:
        self.calls.append({"session_id": session_id, "context": context})


class DummyLearner:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.extract_called = False
        self.index_called = False

    async def extract_knowledge_from_conversation(self, **kwargs: Any) -> List[Dict[str, Any]]:
        self.extract_called = True
        return []

    async def index_extracted_knowledge(self, **kwargs: Any) -> Dict[str, int]:
        self.index_called = True
        return {"indexed": 0}


@pytest.mark.asyncio
async def test_langgraph_knowledge_node_updates_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    session_id = uuid4()
    dummy_memory = DummyMemoryManager()
    db = object()

    async def fake_main_agent(**_: Any) -> ChatResponse:
        return ChatResponse(
            response="Risposta generata",
            session_id=session_id,
            memory_used={},
            tools_used=[],
            tool_details=[],
            notifications_count=0,
            high_urgency_notifications=[],
        )

    monkeypatch.setattr(langgraph_app, "run_main_agent_pipeline", fake_main_agent)

    dummy_learner = DummyLearner()

    import app.services.conversation_learner as conversation_learner_module

    monkeypatch.setattr(
        conversation_learner_module,
        "ConversationLearner",
        lambda *args, **kwargs: dummy_learner,
    )

    class DummySessionContext:
        async def __aenter__(self) -> Any:
            return object()

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

    import app.db.database as database_module

    monkeypatch.setattr(
        database_module,
        "AsyncSessionLocal",
        lambda: DummySessionContext(),
    )

    class DummyToolManager:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def get_available_tools(self) -> List[Dict[str, Any]]:
            return []

        async def execute_tool(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
            return {"success": True, "result": {}}

    monkeypatch.setattr(langgraph_app, "ToolManager", DummyToolManager)

    async def fake_analyze(*args: Any, **kwargs: Any) -> Dict[str, Any]:
        return {"needs_plan": False, "reason": "test", "steps": []}

    monkeypatch.setattr(langgraph_app, "analyze_message_for_plan", fake_analyze)

    created_tasks: List[asyncio.Future[Any]] = []

    original_create_task = asyncio.create_task

    def fake_create_task(
        coro: asyncio.coroutine[Any, Any, Any], *args: Any, **kwargs: Any
    ) -> asyncio.Future[Any]:
        task = original_create_task(coro, *args, **kwargs)
        created_tasks.append(task)
        return task

    monkeypatch.setattr(asyncio, "create_task", fake_create_task)

    request = ChatRequest(message="Ciao", session_id=session_id, use_memory=True)

    # Act
    result = await langgraph_app.run_langgraph_chat(
        db=db,  # type: ignore[arg-type]
        session_id=session_id,
        request=request,
        ollama=object(),  # type: ignore[arg-type]
        memory_manager=dummy_memory,  # type: ignore[arg-type]
        session_context=[],
        retrieved_memory=[],
        memory_used={},
        previous_messages=[{"role": "user", "content": "Messaggio precedente"}],
    )

    for task in created_tasks:
        await task

    # Assert
    chat_response = result["chat_response"]
    assert chat_response.response == "Risposta generata"
    assert dummy_memory.calls, "La memoria breve dovrebbe essere aggiornata"
    context = dummy_memory.calls[0]["context"]
    assert context["last_user_message"] == "Ciao"
    assert context["last_assistant_message"] == "Risposta generata"
    assert context["message_count"] == 3
    assert created_tasks, "L'auto-learning dovrebbe essere schedulato"
    assert dummy_learner.extract_called is True
