from __future__ import annotations

import asyncio
from typing import Any, Dict, List
from uuid import uuid4

import pytest

from app.agents import langgraph_app
from app.models.schemas import ChatRequest, ChatResponse


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

    result_initial = await langgraph_app.run_langgraph_chat(
        db=db,  # type: ignore[arg-type]
        session_id=session_id,
        request=request_initial,
        ollama=object(),  # type: ignore[arg-type]
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
