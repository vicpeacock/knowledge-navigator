from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict
from uuid import UUID

from langgraph.graph import END, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ollama_client import OllamaClient
from app.models.schemas import ChatRequest, ChatResponse
from app.agents.main_agent import run_main_agent_pipeline


class LangGraphChatState(TypedDict, total=False):
    event: Dict[str, Any]
    session_id: UUID
    request: ChatRequest
    db: AsyncSession
    ollama: OllamaClient
    session_context: List[Dict[str, str]]
    retrieved_memory: List[str]
    memory_used: Dict[str, Any]
    messages: List[Dict[str, str]]
    routing_decision: str
    chat_response: ChatResponse


async def event_handler_node(state: LangGraphChatState) -> LangGraphChatState:
    """Normalizza l'evento in arrivo e aggiorna la history."""

    messages = state.get("messages", [])
    event = state.get("event", {})
    role = event.get("role", "user")
    content = event.get("content", "")
    messages.append({"role": role, "content": content})
    state["messages"] = messages
    return state


async def orchestrator_node(state: LangGraphChatState) -> LangGraphChatState:
    """Per ora instrada sempre verso il main agent."""

    state["routing_decision"] = "main"
    return state


async def main_agent_node(state: LangGraphChatState) -> LangGraphChatState:
    """Esegue la pipeline principale riutilizzando la logica legacy."""

    chat_response = await run_main_agent_pipeline(
        db=state["db"],
        session_id=state["session_id"],
        request=state["request"],
        ollama=state["ollama"],
        session_context=state["session_context"],
        retrieved_memory=list(state["retrieved_memory"]),
        memory_used=state["memory_used"],
    )
    state["chat_response"] = chat_response
    return state


def _routing_router(state: LangGraphChatState) -> str:
    return "main_agent"


def build_langgraph_app() -> StateGraph:
    graph = StateGraph(LangGraphChatState)
    graph.add_node("event_handler", event_handler_node)
    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("main_agent", main_agent_node)

    graph.set_entry_point("event_handler")
    graph.add_edge("event_handler", "orchestrator")
    graph.add_conditional_edges("orchestrator", _routing_router, {"main_agent": "main_agent"})
    graph.add_edge("main_agent", END)
    return graph.compile()


async def run_langgraph_chat(
    *,
    db: AsyncSession,
    session_id: UUID,
    request: ChatRequest,
    ollama: OllamaClient,
    session_context: List[Dict[str, str]],
    retrieved_memory: List[str],
    memory_used: Dict[str, Any],
) -> ChatResponse:
    app = build_langgraph_app()
    state: LangGraphChatState = {
        "event": {"role": "user", "content": request.message},
        "session_id": session_id,
        "request": request,
        "db": db,
        "ollama": ollama,
        "session_context": session_context,
        "retrieved_memory": retrieved_memory,
        "memory_used": memory_used,
        "messages": [],
    }
    final_state = await app.ainvoke(state)
    return final_state["chat_response"]

