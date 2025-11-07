"""
Minimal LangGraph prototype for Knowledge Navigator.

This module defines a first draft of the multi-agent orchestration graph using
LangGraph. The goal is to provide a foundation we can iterate on while we port
the existing agents (Main, Integrity, Knowledge, etc.) into the new
architecture.

For now, the implementation is intentionally simple: it normalises an incoming
event, runs a stub integrity check, and generates a placeholder response. This
lets us validate the wiring and state handling without depending on the
full production stack or long-running LLM calls.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, TypedDict
import logging

from langgraph.graph import END, StateGraph

logger = logging.getLogger(__name__)


class LangGraphState(TypedDict, total=False):
    """
    Shared state carried across the graph execution.

    Keys are optional because nodes may add information progressively.
    """

    event: Dict[str, Any]
    messages: List[Dict[str, str]]
    context: Dict[str, Any]
    integrity_report: Dict[str, Any]
    response: str
    notifications: List[Dict[str, Any]]


def _ensure_messages(history: Optional[List[Dict[str, str]]] = None) -> List[Dict[str, str]]:
    """
    Normalise the conversation history list.
    """

    if history is None:
        return []
    return list(history)


async def event_handler_node(state: LangGraphState) -> LangGraphState:
    """
    Entry point for the graph.

    Normalises the incoming event and appends it to the message history.
    """

    event = state.get("event", {})
    messages = _ensure_messages(state.get("messages"))

    if not event:
        logger.warning("LangGraph prototype: received empty event")
        return state

    role = event.get("role", "user")
    content = event.get("content", "")

    messages.append({"role": role, "content": content})
    state["messages"] = messages

    logger.debug("LangGraph prototype: event normalised (role=%s)", role)
    return state


async def orchestrator_node(state: LangGraphState) -> LangGraphState:
    """
    Decides which agents should run for the current event.

    For the prototype we keep it simple:
    - If the last message comes from the user, run integrity + main agents.
    - Otherwise, only the main agent responds (e.g., system prompts).
    """

    messages = _ensure_messages(state.get("messages"))
    decision: Literal["integrity", "main"] = "main"

    if messages and messages[-1].get("role") == "user":
        decision = "integrity"

    state["context"] = {
        **state.get("context", {}),
        "routing_decision": decision,
    }

    logger.debug("LangGraph prototype: routing decision=%s", decision)
    return state


async def integrity_agent_node(state: LangGraphState) -> LangGraphState:
    """
    Stub integrity agent.

    The real implementation will delegate to the existing SemanticIntegrityChecker.
    For now, we simply record that the check was executed.
    """

    messages = _ensure_messages(state.get("messages"))
    last_message = messages[-1] if messages else {"content": ""}

    state["integrity_report"] = {
        "status": "checked",
        "summary": f"Prototype integrity check executed for: {last_message.get('content', '')[:60]}",
    }

    logger.debug("LangGraph prototype: integrity check stub executed")
    return state


async def main_agent_node(state: LangGraphState) -> LangGraphState:
    """
    Stub main agent.

    The production version will reuse the existing Main chat pipeline. Here we
    generate a short acknowledgement so the prototype can run without LLM calls.
    """

    messages = _ensure_messages(state.get("messages"))
    user_content = ""

    if messages:
        user_messages = [msg for msg in messages if msg.get("role") == "user"]
        user_content = user_messages[-1]["content"] if user_messages else messages[-1].get("content", "")

    integrity_summary = state.get("integrity_report", {}).get("summary")
    if integrity_summary:
        logger.debug("LangGraph prototype: integrity summary available for response")

    response_parts = [
        "LangGraph prototype attivo.",
        f"Ultimo messaggio utente: {user_content!r}" if user_content else "Nessun messaggio utente trovato.",
    ]

    if integrity_summary:
        response_parts.append(f"[Integrity] {integrity_summary}")

    state["response"] = " ".join(response_parts)

    logger.debug("LangGraph prototype: main agent stub generated response")
    return state


def _orchestrator_router(state: LangGraphState) -> str:
    """
    Router helper for LangGraph.

    Turns the routing decision stored in state into the next node identifier.
    """

    routing_decision = state.get("context", {}).get("routing_decision")
    if routing_decision == "integrity":
        return "integrity_agent"
    return "main_agent"


def build_langgraph_prototype() -> StateGraph:
    """
    Build and compile the minimal LangGraph application.

    Returns:
        Compiled LangGraph application ready to be invoked with a state payload.
    """

    graph = StateGraph(LangGraphState)

    graph.add_node("event_handler", event_handler_node)
    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("integrity_agent", integrity_agent_node)
    graph.add_node("main_agent", main_agent_node)

    graph.set_entry_point("event_handler")
    graph.add_edge("event_handler", "orchestrator")
    graph.add_conditional_edges("orchestrator", _orchestrator_router, {"integrity_agent": "integrity_agent", "main_agent": "main_agent"})
    graph.add_edge("integrity_agent", "main_agent")
    graph.add_edge("main_agent", END)

    logger.info("LangGraph prototype compiled")
    return graph.compile()


async def run_prototype_event(content: str, role: str = "user") -> LangGraphState:
    """
    Convenience helper to execute the prototype end-to-end.

    Args:
        content: Message content to feed into the graph.
        role: Role associated with the event (default: ``user``).

    Returns:
        Final state produced by the compiled graph.
    """

    app = build_langgraph_prototype()
    initial_state: LangGraphState = {
        "event": {
            "role": role,
            "content": content,
        }
    }
    return await app.ainvoke(initial_state)

