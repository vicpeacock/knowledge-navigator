from __future__ import annotations

import asyncio
from typing import Any, Dict, List
from uuid import uuid4

import pytest

from app.agents import langgraph_app
from app.models.schemas import ChatRequest, ChatResponse
from app.services.agent_activity_stream import AgentActivityStream
from app.services.task_queue import TaskQueue


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    try:
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        if pending:
            loop.run_until_complete(
                asyncio.gather(*pending, return_exceptions=True)
            )
        loop.run_until_complete(loop.shutdown_asyncgens())
    finally:
        asyncio.set_event_loop(None)
        loop.close()


def test_should_force_web_search_acknowledgement_off() -> None:
    request = ChatRequest(
        message="Si, grazie",
        session_id=uuid4(),
        use_memory=False,
        force_web_search=True,
    )

    assert langgraph_app.should_force_web_search(request, True) is False


def test_should_force_web_search_keywords_on() -> None:
    request = ChatRequest(
        message="Puoi cercare sul web le ultime news su SpaceX?",
        session_id=uuid4(),
        use_memory=False,
        force_web_search=True,
    )

    assert langgraph_app.should_force_web_search(request, False) is True


@pytest.mark.asyncio
async def test_plan_waits_for_confirmation_and_resumes(monkeypatch: pytest.MonkeyPatch) -> None:
    session_id = uuid4()
    db = object()

    # Stub ToolManager
    class PlanningToolManager:
        executed: List[Dict[str, Any]] = []

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def get_available_tools(self) -> List[Dict[str, Any]]:
            return [
                {"name": "web_search", "description": "Ricerca web"},
                {"name": "get_emails", "description": "Recupera email"},
            ]

        async def execute_tool(
            self,
            tool_name: str,
            inputs: Dict[str, Any],
            db: Any = None,
            session_id: Any = None,
        ) -> Dict[str, Any]:
            PlanningToolManager.executed.append({"tool": tool_name, "inputs": inputs})
            return {"success": True, "result": {"content": "informazioni mittente"}}

    PlanningToolManager.executed = []

    monkeypatch.setattr(langgraph_app, "ToolManager", PlanningToolManager)

    plan_calls: List[str] = []

    async def fake_analyze(*args: Any, **kwargs: Any) -> Dict[str, Any]:
        plan_calls.append("called")
        return {
            "needs_plan": True,
            "reason": "Analisi automatica della richiesta email",
            "steps": [
                {
                    "description": "Ho bisogno della tua conferma prima di leggere l'ultima email ricevuta.",
                    "action": "wait_user",
                },
                {
                    "description": "Recupero l'ultima email per analizzare il mittente.",
                    "action": "tool",
                    "tool": "get_emails",
                    "inputs": {"max_results": 1, "include_body": True},
                },
                {
                    "description": "Rispondo all'utente con le informazioni sul mittente.",
                    "action": "respond",
                },
            ],
        }

    monkeypatch.setattr(langgraph_app, "analyze_message_for_plan", fake_analyze)

    async def fake_summary(*args: Any, **kwargs: Any) -> str:
        return "Ho letto l'ultima email e ti ho riportato le informazioni principali."

    monkeypatch.setattr(langgraph_app, "summarize_plan_results", fake_summary)

    async def fake_main_agent(**kwargs: Any) -> ChatResponse:
        raise AssertionError("run_main_agent_pipeline should not be called in plan flow")

    monkeypatch.setattr(langgraph_app, "run_main_agent_pipeline", fake_main_agent)

    request_initial = ChatRequest(
        message="Puoi leggermi l'ultima email del mittente dell'ultimo messaggio?",
        session_id=session_id,
        use_memory=False,
        force_web_search=False,
    )

    planner_stub = object()
    activity_stream = AgentActivityStream()

    result_initial = await langgraph_app.run_langgraph_chat(
        db=db,  # type: ignore[arg-type]
        session_id=session_id,
        request=request_initial,
        ollama=object(),  # type: ignore[arg-type]
        planner_client=planner_stub,  # type: ignore[arg-type]
        agent_activity_stream=activity_stream,
        memory_manager=object(),  # type: ignore[arg-type]
        session_context=[],
        retrieved_memory=[],
        memory_used={},
        previous_messages=[],
        pending_plan=None,
    )

    initial_response = result_initial["chat_response"].response
    assert "conferma" in initial_response.lower()
    assert result_initial["plan_metadata"] is not None
    assert not result_initial["assistant_message_saved"]
    assert PlanningToolManager.executed == []
    notifications_initial = result_initial["chat_response"].high_urgency_notifications
    statuses_initial = [n["content"].get("status") for n in notifications_initial]
    assert "generated" in statuses_initial
    assert "waiting_confirmation" in statuses_initial
    activity_initial = result_initial["chat_response"].agent_activity
    match = (
        lambda evt, agent_id, status: (
            (
                evt.get("agent_id") == agent_id
                and evt.get("status") == status
            )
            if isinstance(evt, dict)
            else (
                getattr(evt, "agent_id", None) == agent_id
                and getattr(evt, "status", None) == status
            )
        )
    )
    assert any(
        match(evt, "planner", "completed") for evt in activity_initial
    ), "Il planner dovrebbe avere telemetria completata"
    assert any(
        match(evt, "tool_loop", "waiting") for evt in activity_initial
    ), "La tool_loop dovrebbe essere in attesa della conferma utente"

    request_confirm = ChatRequest(
        message="Sì, grazie",
        session_id=session_id,
        use_memory=False,
        force_web_search=True,
    )

    result_followup = await langgraph_app.run_langgraph_chat(
        db=db,  # type: ignore[arg-type]
        session_id=session_id,
        request=request_confirm,
        ollama=object(),  # type: ignore[arg-type]
        planner_client=planner_stub,  # type: ignore[arg-type]
        agent_activity_stream=activity_stream,
        memory_manager=object(),  # type: ignore[arg-type]
        session_context=[{"role": "assistant", "content": initial_response}],
        retrieved_memory=[],
        memory_used={},
        previous_messages=[{"role": "assistant", "content": initial_response}],
        pending_plan=result_initial["plan_metadata"],
    )

    followup_response = result_followup["chat_response"].response
    assert "informazioni principali" in followup_response
    assert result_followup["plan_metadata"] is None
    assert PlanningToolManager.executed and PlanningToolManager.executed[0]["tool"] == "get_emails"
    assert len(plan_calls) == 1
    notifications_followup = result_followup["chat_response"].high_urgency_notifications
    statuses_followup = [n["content"].get("status") for n in notifications_followup]
    assert "completed" in statuses_followup or "partial" in statuses_followup
    activity_followup = result_followup["chat_response"].agent_activity
    assert any(
        match(evt, "tool_loop", "completed") for evt in activity_followup
    ), "La tool_loop dovrebbe completare il piano dopo la conferma"


@pytest.mark.asyncio
async def test_contradiction_task_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core import dependencies
    from app.services.task_queue import Task, TaskPriority, TaskStatus

    session_id = uuid4()
    db = object()

    queue = TaskQueue()
    monkeypatch.setattr(dependencies, "_task_queue", queue, raising=False)

    contradiction_task = Task(
        type="resolve_contradiction",
        payload={
            "new_statement": "Il contratto è stato rinnovato",
            "contradictions": [
                {
                    "existing_memory": "Il contratto non è stato rinnovato",
                    "explanation": "Due affermazioni opposte",
                }
            ],
        },
        origin="background_integrity_agent",
        priority=TaskPriority.HIGH,
    )
    queue.enqueue(session_id, contradiction_task)

    async def fake_main_agent(**kwargs: Any) -> ChatResponse:
        raise AssertionError("run_main_agent_pipeline should not be called when handling task queue")

    monkeypatch.setattr(langgraph_app, "run_main_agent_pipeline", fake_main_agent)

    planner_stub = object()
    activity_stream = AgentActivityStream()

    request_user = ChatRequest(
        message="Puoi controllare lo stato del contratto?",
        session_id=session_id,
        use_memory=False,
        force_web_search=False,
    )

    first_result = await langgraph_app.run_langgraph_chat(
        db=db,  # type: ignore[arg-type]
        session_id=session_id,
        request=request_user,
        ollama=object(),  # type: ignore[arg-type]
        planner_client=planner_stub,  # type: ignore[arg-type]
        agent_activity_stream=activity_stream,
        memory_manager=object(),  # type: ignore[arg-type]
        session_context=[],
        retrieved_memory=[],
        memory_used={},
        previous_messages=[],
        pending_plan=None,
    )

    response_text = first_result["chat_response"].response
    assert "contraddizione" in response_text.lower()
    task_waiting = queue.find_task_by_status(session_id, TaskStatus.WAITING_USER)
    assert task_waiting is not None

    request_answer = ChatRequest(
        message="La versione corretta è che il contratto è stato rinnovato.",
        session_id=session_id,
        use_memory=False,
        force_web_search=False,
    )

    second_result = await langgraph_app.run_langgraph_chat(
        db=db,  # type: ignore[arg-type]
        session_id=session_id,
        request=request_answer,
        ollama=object(),  # type: ignore[arg-type]
        planner_client=planner_stub,  # type: ignore[arg-type]
        agent_activity_stream=activity_stream,
        memory_manager=object(),  # type: ignore[arg-type]
        session_context=[{"role": "assistant", "content": response_text}],
        retrieved_memory=[],
        memory_used={},
        previous_messages=[{"role": "assistant", "content": response_text}],
        pending_plan=None,
    )

    completion_text = second_result["chat_response"].response
    assert "grazie" in completion_text.lower()
    final_task = queue.get_task(session_id, contradiction_task.id)
    assert final_task is not None
    assert final_task.status == TaskStatus.COMPLETED
