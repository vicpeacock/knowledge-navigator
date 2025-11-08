from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional, TypedDict
from uuid import UUID

from langgraph.graph import END, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ollama_client import OllamaClient
from app.models.schemas import ChatRequest, ChatResponse
from app.agents.main_agent import run_main_agent_pipeline
from app.services.memory_manager import MemoryManager


class LangGraphChatState(TypedDict, total=False):
    event: Dict[str, Any]
    session_id: UUID
    request: ChatRequest
    db: AsyncSession
    ollama: OllamaClient
    memory_manager: MemoryManager
    session_context: List[Dict[str, str]]
    retrieved_memory: List[str]
    memory_used: Dict[str, Any]
    messages: List[Dict[str, str]]
    tool_calls: List[Dict[str, Any]]
    tool_results: List[Dict[str, Any]]
    notifications: List[Dict[str, Any]]
    previous_messages: List[Dict[str, str]]
    routing_decision: str
    response: Optional[str]
    chat_response: Optional[ChatResponse]
    done: bool


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

    state["routing_decision"] = "tool_loop"
    return state


async def tool_loop_node(state: LangGraphChatState) -> LangGraphChatState:
    """Stub iniziale del ciclo tool/LLM: delega alla pipeline principale."""

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
    state["response"] = chat_response.response
    state["done"] = True
    return state


async def knowledge_agent_node(state: LangGraphChatState) -> LangGraphChatState:
    """Aggiorna la memoria breve e avvia auto-learning in background se necessario."""

    request = state["request"]
    if not request.use_memory:
        return state

    memory_manager = state.get("memory_manager")
    if memory_manager is None:
        return state

    response_text = state.get("response")
    if not response_text:
        chat_response = state.get("chat_response")
        if chat_response:
            response_text = chat_response.response

    if not response_text:
        return state

    logger = logging.getLogger(__name__)

    # Update short-term memory with the latest exchange
    try:
        new_context = {
            "last_user_message": request.message,
            "last_assistant_message": response_text,
            "message_count": len(state.get("previous_messages", [])) + 2,
        }
        await memory_manager.update_short_term_memory(
            state["db"],
            state["session_id"],
            new_context,
        )
        state.setdefault("memory_used", {})["short_term"] = True
    except Exception:  # pragma: no cover - log warning
        logger.warning("Errore nell'aggiornamento della memoria breve", exc_info=True)

    # Prepare recent conversation window for knowledge extraction
    previous_messages = state.get("previous_messages", [])
    recent_messages = previous_messages[-8:]
    recent_messages.append({"role": "user", "content": request.message})
    recent_messages.append({"role": "assistant", "content": response_text})

    if len(recent_messages) < 2:
        logger.info("⏭️ Skip auto-learning: conversazione insufficiente (%s messaggi)", len(recent_messages))
        return state

    try:
        from app.services.conversation_learner import ConversationLearner
        from app.db.database import AsyncSessionLocal

        learner = ConversationLearner(memory_manager=memory_manager, ollama_client=state["ollama"])

        async def _extract_knowledge_background() -> None:
            async with AsyncSessionLocal() as db_session:
                try:
                    logger.info("🔍 Estrazione conoscenza da %s messaggi", len(recent_messages))
                    knowledge_items = await learner.extract_knowledge_from_conversation(
                        db=db_session,
                        session_id=state["session_id"],
                        messages=recent_messages,
                        min_importance=0.6,
                    )

                    if knowledge_items:
                        stats = await learner.index_extracted_knowledge(
                            db=db_session,
                            knowledge_items=knowledge_items,
                            session_id=state["session_id"],
                        )
                        logger.info("✅ Auto-learning completato: %s elementi indicizzati", stats.get("indexed", 0))
                    else:
                        logger.info("ℹ️ Nessuna conoscenza estratta (soglia importanza non superata)")
                except Exception:
                    logger.warning("Errore nell'auto-learning in background", exc_info=True)

        asyncio.create_task(_extract_knowledge_background())
    except Exception:
        logger.warning("Impossibile avviare auto-learning", exc_info=True)

    return state


async def integrity_agent_node(state: LangGraphChatState) -> LangGraphChatState:
    """Segnaposto per SemanticIntegrityChecker (per ora no-op)."""

    return state


async def notification_collector_node(state: LangGraphChatState) -> LangGraphChatState:
    """Segnaposto per NotificationService (per ora no-op)."""

    return state


async def response_formatter_node(state: LangGraphChatState) -> LangGraphChatState:
    """Garantisce che un ChatResponse sia presente nello stato finale."""

    if "chat_response" not in state or state["chat_response"] is None:
        state["chat_response"] = ChatResponse(
            response=state.get("response", ""),
            session_id=state["session_id"],
            memory_used=state.get("memory_used", {}),
            tools_used=[],
            tool_details=[],
            notifications_count=len(state.get("notifications", [])),
            high_urgency_notifications=state.get("notifications", []),
        )
    return state


def _routing_router(state: LangGraphChatState) -> str:
    return "tool_loop"


def build_langgraph_app() -> StateGraph:
    graph = StateGraph(LangGraphChatState)
    graph.add_node("event_handler", event_handler_node)
    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("tool_loop", tool_loop_node)
    graph.add_node("knowledge_agent", knowledge_agent_node)
    graph.add_node("integrity_agent", integrity_agent_node)
    graph.add_node("notification_collector", notification_collector_node)
    graph.add_node("response_formatter", response_formatter_node)

    graph.set_entry_point("event_handler")
    graph.add_edge("event_handler", "orchestrator")
    graph.add_conditional_edges(
        "orchestrator",
        _routing_router,
        {
            "tool_loop": "tool_loop",
        },
    )
    graph.add_edge("tool_loop", "knowledge_agent")
    graph.add_edge("knowledge_agent", "integrity_agent")
    graph.add_edge("integrity_agent", "notification_collector")
    graph.add_edge("notification_collector", "response_formatter")
    graph.add_edge("response_formatter", END)
    return graph.compile()


async def run_langgraph_chat(
    *,
    db: AsyncSession,
    session_id: UUID,
    request: ChatRequest,
    ollama: OllamaClient,
    memory_manager: MemoryManager,
    session_context: List[Dict[str, str]],
    retrieved_memory: List[str],
    memory_used: Dict[str, Any],
    previous_messages: Optional[List[Dict[str, str]]] = None,
) -> ChatResponse:
    app = build_langgraph_app()
    state: LangGraphChatState = {
        "event": {"role": "user", "content": request.message},
        "session_id": session_id,
        "request": request,
        "db": db,
        "ollama": ollama,
        "memory_manager": memory_manager,
        "session_context": session_context,
        "retrieved_memory": retrieved_memory,
        "memory_used": memory_used,
        "messages": [],
        "tool_calls": [],
        "tool_results": [],
        "notifications": [],
        "previous_messages": previous_messages or [],
        "done": False,
    }
    final_state = await app.ainvoke(state)
    return final_state["chat_response"]

