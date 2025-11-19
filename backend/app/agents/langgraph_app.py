from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional, TypedDict
from uuid import UUID, uuid4

from langgraph.graph import END, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ollama_client import OllamaClient
from app.models.notifications import (
    Notification,
    NotificationChannel,
    NotificationPayload,
    NotificationPriority,
    NotificationSource,
)
from app.models.schemas import ChatRequest, ChatResponse, ToolExecutionDetail
from app.agents.main_agent import run_main_agent_pipeline
from app.core.memory_manager import MemoryManager
from app.core.tool_manager import ToolManager
from app.services.agent_activity_stream import AgentActivityStream
from app.services.notification_center import NotificationCenter
from app.services.task_queue import TaskQueue, Task, TaskStatus
from app.core.dependencies import get_task_queue
from app.services.task_queue import TaskQueue, Task, TaskStatus


class PlanStep(TypedDict, total=False):
    id: int
    description: str
    action: str  # tool | respond | wait_user
    tool: Optional[str]
    inputs: Dict[str, Any]
    status: str
    result_preview: Optional[str]
    error: Optional[str]


class LangGraphResult(TypedDict):
    chat_response: ChatResponse
    plan_metadata: Optional[Dict[str, Any]]
    assistant_message_saved: bool


ACK_REGEX = re.compile(
    r"^(ok|okay|va bene|va bene\s*si|va bene\s*sì|va pure|vai pure|procedi|continua|fai pure|perfetto|d'accordo|si|sì|si grazie|sì grazie|si, grazie|sì, grazie|ok grazie|ok, grazie|certo|certo, grazie|thanks|grazie|yes please|yes, please|go ahead|do it|per favore|esegui|fallo)([!.]*)$",
    re.IGNORECASE,
)

IGNORE_REGEX = re.compile(
    r"^(ignora|ignora\s+questa|ignora\s+la|ignora\s+questa\s+contraddizione|ignora\s+la\s+contraddizione|skip|salta)([!.]*)$",
    re.IGNORECASE,
)

NO_CONTRADICTION_REGEX = re.compile(
    r"(non\s+c'è\s+contraddizione|non\s+ci\s+sono\s+contraddizioni|non\s+è\s+una\s+contraddizione|non\s+esiste\s+contraddizione)",
    re.IGNORECASE,
)


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def is_acknowledgement(message: str) -> bool:
    if not message:
        return False
    normalized = _normalize_text(message)
    if not normalized:
        return False
    if len(normalized) > 40:
        return False
    if normalized in {"ok", "okay", "va bene", "va bene si", "va bene sì", "si", "sì", "si grazie", "sì grazie", "si, grazie", "sì, grazie", "grazie", "certo", "perfetto", "d'accordo", "procedi", "continua", "vai pure", "fai pure"}:
        return True
    return bool(ACK_REGEX.match(normalized))


def is_ignore_contradiction(message: str) -> bool:
    """Check if the user wants to ignore the contradiction."""
    if not message:
        return False
    normalized = _normalize_text(message)
    if not normalized:
        return False
    # Check if message starts with ignore pattern
    return bool(IGNORE_REGEX.match(normalized))


def is_no_contradiction(message: str) -> bool:
    """Check if the user claims there's no contradiction."""
    if not message:
        return False
    normalized = _normalize_text(message)
    if not normalized:
        return False
    # Check if message contains "non c'è contraddizione" pattern
    # Allow up to 3 words before the pattern (e.g., "secondo me non c'è contraddizione")
    match = NO_CONTRADICTION_REGEX.search(normalized)
    if match:
        start_pos = match.start()
        # Allow up to 3 words before the pattern
        words_before = normalized[:start_pos].strip().split() if start_pos > 0 else []
        return len(words_before) <= 3
    return False


def should_force_web_search(request: ChatRequest, acknowledgement: bool) -> bool:
    if not request.force_web_search:
        return False
    if acknowledgement:
        return False
    message = _normalize_text(request.message)
    if not message:
        return False
    if len(message) < 20 and "?" not in request.message:
        return False
    keywords = [
        "cerca",
        "cercare",
        "ricerca",
        "web",
        "internet",
        "google",
        "news",
        "aggiornamenti",
        "informazioni",
        "ultime",
        "notizie",
    ]
    return any(keyword in message for keyword in keywords)


def build_tool_catalog(tools: List[Dict[str, Any]]) -> str:
    catalog_lines = []
    for tool in tools:
        name = tool.get("name", "")
        description = tool.get("description", "")
        catalog_lines.append(f"- {name}: {description}")
    return "\n".join(catalog_lines)


def safe_json_loads(raw: str) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        try:
            cleaned = raw.strip().strip("`")
            return json.loads(cleaned)
        except Exception:
            return None


def normalize_plan_steps(plan_payload: List[Dict[str, Any]], available_tool_names: List[str]) -> List[PlanStep]:
    normalized_steps: List[PlanStep] = []
    for idx, raw_step in enumerate(plan_payload, start=1):
        if not isinstance(raw_step, dict):
            continue
        action = raw_step.get("action") or ("tool" if raw_step.get("tool") else "respond")
        action = str(action).lower()
        if action not in {"tool", "respond", "wait_user"}:
            action = "tool" if raw_step.get("tool") else "respond"

        tool_name = raw_step.get("tool")
        if tool_name and tool_name not in available_tool_names:
            tool_name = None
            if action == "tool":
                action = "respond"

        inputs = raw_step.get("inputs")
        if not isinstance(inputs, dict):
            inputs = {}

        description = raw_step.get("description") or raw_step.get("step") or ""
        description = str(description).strip()

        normalized_steps.append(
            PlanStep(
                id=idx,
                description=description,
                action=action,
                tool=tool_name,
                inputs=inputs,
                status=raw_step.get("status", "pending"),
                result_preview=raw_step.get("result_preview"),
                error=raw_step.get("error"),
            )
        )
    return normalized_steps


def serialize_plan_for_notification(plan: List[PlanStep]) -> List[Dict[str, Any]]:
    serialized: List[Dict[str, Any]] = []
    for step in plan:
        serialized.append(
            {
                "id": step.get("id"),
                "description": step.get("description"),
                "action": step.get("action"),
                "tool": step.get("tool"),
                "status": step.get("status"),
            }
        )
    return serialized


_AGENT_REGISTRY: Dict[str, str] = {
    "event_handler": "Event Handler",
    "orchestrator": "Orchestrator",
    "tool_loop": "Tool Loop",
    "planner": "Planner",
    "knowledge_agent": "Knowledge Agent",
    "notification_collector": "Notification Collector",
    "response_formatter": "Response Formatter",
    "task_dispatcher": "Task Dispatcher",
    "background_integrity_agent": "Background Integrity Agent",
    "service_health_agent": "Service Health Agent",
    "event_monitor": "Event Monitor",
}


def log_agent_activity(
    state: LangGraphChatState,
    *,
    agent_id: str,
    status: str,
    message: Optional[str] = None,
    agent_name: Optional[str] = None,
) -> None:
    """Append a telemetry event describing the activity of an agent node."""

    if status not in {"started", "completed", "waiting", "error"}:
        logging.getLogger(__name__).debug("Ignoring unsupported agent status %s", status)
        return

    entry = {
        "agent_id": agent_id,
        "agent_name": agent_name or _AGENT_REGISTRY.get(agent_id, agent_id.replace("_", " ").title()),
        "status": status,
        "message": message,
        "timestamp": datetime.now(UTC),
    }
    state.setdefault("agent_activity", []).append(entry)

    manager = state.get("agent_activity_manager")
    session_id = state.get("session_id")
    logger = logging.getLogger(__name__)
    if manager and session_id:
        logger.info("📡 Publishing agent activity: %s (%s) for session %s", agent_id, status, session_id)
        manager.publish(session_id, entry)
    else:
        logger.warning("⚠️  Cannot publish agent activity: manager=%s, session_id=%s", manager is not None, session_id is not None)


def _ensure_notification_center(state: LangGraphChatState) -> NotificationCenter:
    center = state.get("notification_center")
    if not center:
        center = NotificationCenter()
        state["notification_center"] = center
    return center


def _snapshot_notifications(state: LangGraphChatState) -> None:
    center = state.get("notification_center")
    if not center:
        state["notifications"] = []
        state["high_urgency_notifications"] = []
        return

    all_notifications = center.as_transport()
    high_notifications = center.as_transport(min_priority=NotificationPriority.MEDIUM)
    if not high_notifications:
        high_notifications = all_notifications

    state["notifications"] = all_notifications
    state["high_urgency_notifications"] = high_notifications


def _handle_active_task(
    state: LangGraphChatState,
    task: Task,
    queue: TaskQueue,
) -> Optional[tuple[LangGraphChatState, str]]:
    if task.type == "resolve_contradiction":
        return _handle_contradiction_resolution_task(state, task, queue)
    return None


def _handle_contradiction_resolution_task(
    state: LangGraphChatState,
    task: Task,
    queue: TaskQueue,
) -> Optional[tuple[LangGraphChatState, str]]:
    logger = logging.getLogger(__name__)
    session_id = state.get("session_id")
    if not session_id:
        return None

    payload = task.payload or {}
    if task.status == TaskStatus.IN_PROGRESS:
        # For contradictions, we don't send messages to chat - they appear in the notification bell
        # Just update the task status to WAITING_USER
        queue.update_task(
            session_id,
            task.id,
            status=TaskStatus.WAITING_USER,
            payload_updates={"prompt_sent_at": datetime.now(UTC).isoformat()},
        )
        state["current_task"] = queue.get_task(session_id, task.id)
        
        # Don't create a chat message - the notification is already in the bell
        # Just mark as done so the dispatcher can move on
        state["response"] = ""  # Empty response - no message in chat
        state["plan_completed"] = True
        state["assistant_message_saved"] = True  # Mark as saved so no message is persisted
        state.setdefault("tool_results", [])
        _snapshot_notifications(state)
        notifications = state.get("notifications", [])
        high_notifications = state.get("high_urgency_notifications", [])
        state["chat_response"] = ChatResponse(
            response="",  # Empty - notification is in the bell, not in chat
            session_id=session_id,
            memory_used=state.get("memory_used", {}),
            tools_used=[],
            tool_details=[],
            notifications_count=len(notifications),
            high_urgency_notifications=high_notifications,
            agent_activity=state.get("agent_activity", []),
        )
        log_agent_activity(
            state,
            agent_id="task_dispatcher",
            status="waiting",
            message="Contradiction resolution awaiting user input (notification bell)",
        )
        return state, "completed"  # Mark as completed so dispatcher doesn't wait

    if task.status == TaskStatus.WAITING_USER:
        user_reply = state["request"].message.strip()
        
        # Determine response type
        if is_ignore_contradiction(user_reply):
            resolution_type = "ignored"
            acknowledgement = "Ho ignorato questa contraddizione come richiesto."
        elif is_no_contradiction(user_reply):
            resolution_type = "no_contradiction"
            # Extract explanation if present
            normalized = _normalize_text(user_reply)
            match = NO_CONTRADICTION_REGEX.search(normalized)
            if match:
                # Find the corresponding position in the original message
                # This is approximate but should work for most cases
                explanation_part = user_reply[match.end():].strip()
                if explanation_part:
                    explanation = explanation_part
                else:
                    explanation = user_reply
            else:
                explanation = user_reply
            acknowledgement = f"Grazie per la spiegazione. Ho preso nota che non c'è contraddizione: {explanation}"
        else:
            resolution_type = "resolved"
            acknowledgement = "Grazie! Terrò conto della tua indicazione per mantenere coerenti le informazioni."
        
        queue.complete_task(
            session_id,
            task.id,
            payload_updates={
                "user_response": user_reply,
                "resolution_type": resolution_type,
                "resolved_at": datetime.now(UTC).isoformat(),
            },
        )
        state["current_task"] = None
        
        # Trigger dispatcher to process next queued task if any
        try:
            from app.core.dependencies import get_task_dispatcher
            dispatcher = get_task_dispatcher()
            if dispatcher:
                dispatcher.schedule_dispatch(session_id)
        except Exception as exc:
            logger.warning(
                "Failed to trigger dispatcher for next task after contradiction resolution: %s",
                exc,
            )
        
        state["response"] = acknowledgement
        state["plan_completed"] = True
        state["assistant_message_saved"] = False
        state.setdefault("tool_results", [])
        _snapshot_notifications(state)
        notifications = state.get("notifications", [])
        high_notifications = state.get("high_urgency_notifications", [])
        state["chat_response"] = ChatResponse(
            response=acknowledgement,
            session_id=session_id,
            memory_used=state.get("memory_used", {}),
            tools_used=[],
            tool_details=[],
            notifications_count=len(notifications),
            high_urgency_notifications=high_notifications,
            agent_activity=state.get("agent_activity", []),
        )
        log_agent_activity(
            state,
            agent_id="task_dispatcher",
            status="completed",
            message=f"Contradiction resolution recorded (type: {resolution_type})",
        )
        return state, "completed"

    return None


def _format_contradiction_prompt(payload: Dict[str, Any]) -> str:
    new_statement = payload.get("new_statement") or payload.get("knowledge_item", "")
    contradictions = payload.get("contradictions", []) or []

    lines = [
        "Ho rilevato una possibile contraddizione nelle informazioni memorizzate.",
    ]
    if new_statement:
        lines.append(f"- Nuova informazione: {new_statement}")

    if contradictions:
        lines.append("Memorie in conflitto:")
        for idx, contradiction in enumerate(contradictions[:3], start=1):
            existing = contradiction.get("existing_memory") or contradiction.get("existing")
            explanation = contradiction.get("explanation")
            if existing:
                lines.append(f"  {idx}. {existing}")
            if explanation:
                lines.append(f"     Motivo segnalato: {explanation}")

    lines.append("")
    lines.append("Come vuoi procedere?")
    lines.append("1) Indicare quale versione è corretta o fornire un contesto per conciliare le informazioni")
    lines.append("2) Ignorare questa contraddizione (rispondi con 'ignora' o 'ignora questa contraddizione')")
    lines.append("3) Spiegare perché la contraddizione rilevata in realtà non esiste (rispondi con 'non c'è contraddizione' seguito dalla tua spiegazione)")
    lines.append("")
    lines.append("Puoi rispondere con una delle opzioni sopra o fornire direttamente la tua indicazione.")
    return "\n".join(lines)


def log_planning_status(
    state: LangGraphChatState,
    *,
    status: str,
    reason: Optional[str] = None,
    plan: Optional[List[PlanStep]] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    center = _ensure_notification_center(state)

    priority = NotificationPriority.MEDIUM
    if status in {"waiting_confirmation", "failed"}:
        priority = NotificationPriority.HIGH
    elif status in {"analysis"}:
        priority = NotificationPriority.LOW

    payload_data: Dict[str, Any] = {"status": status, "status_update": True}
    if reason:
        payload_data["reason"] = reason
    if plan:
        payload_data["plan"] = serialize_plan_for_notification(plan)
    if extra:
        payload_data.update(extra)

    notification = Notification(
        id=str(uuid4()),
        type="planning.status",
        priority=priority,
        channel=NotificationChannel.IMMEDIATE,
        source=NotificationSource(agent="planner", feature="tool_loop"),
        payload=NotificationPayload(
            title="Aggiornamento piano",
            message=f"Stato pianificazione: {status}",
            summary=reason,
            data=payload_data,
        ),
        tags=["planning"],
    )
    center.publish(notification)
    _snapshot_notifications(state)


async def analyze_message_for_plan(
    planner_client: Optional[OllamaClient],
    request: ChatRequest,
    available_tools: List[Dict[str, Any]],
    session_context: List[Dict[str, str]],
    ollama_client: Optional[OllamaClient] = None,
) -> Dict[str, Any]:
    tool_catalog = build_tool_catalog(available_tools)
    analysis_prompt = (
        "Analizza la richiesta dell'utente e valuta se servono tool per rispondere.\n"
        f"Tool disponibili:\n{tool_catalog if tool_catalog else '- Nessun tool disponibile'}\n\n"
        "Rispondi con JSON:\n"
        "{\n"
        "  \"needs_plan\": true|false,\n"
        "  \"reason\": \"spiega perché\",\n"
        "  \"steps\": [\n"
        "     {\n"
        "        \"description\": \"testo\",\n"
        "        \"action\": \"tool|respond|wait_user\",\n"
        "        \"tool\": \"nome_tool_o_null\",\n"
        "        \"inputs\": { ... }\n"
        "     }\n"
        "  ]\n"
        "}\n"
    )

    system_prompt = (
        "Sei un pianificatore. Valuta se la richiesta richiede tool esterni. Se sì, crea un piano con steps. Se no, needs_plan=false."
    )

    try:
        client = planner_client or ollama_client
        if client is None:
            logging.getLogger(__name__).warning("Planner client is None, using fallback")
            return {"needs_plan": False, "reason": "planner_unavailable", "steps": []}
        response = await client.generate(
            prompt=analysis_prompt + f"\n\nRichiesta utente:\n{request.message}",
            context=session_context[-3:] if session_context else None,
            system=system_prompt,
        )
        content = response.get("message", {}).get("content", "")
        parsed = safe_json_loads(content)
        if isinstance(parsed, dict):
            return parsed
    except Exception as exc:
        logging.getLogger(__name__).warning(f"Planner analysis failed: {exc}", exc_info=True)

    return {"needs_plan": False, "reason": "fallback", "steps": []}


async def summarize_plan_results(
    ollama: OllamaClient,
    request: ChatRequest,
    session_context: List[Dict[str, str]],
    retrieved_memory: List[str],
    plan: List[PlanStep],
    execution_summaries: List[str],
) -> str:
    plan_summary_lines = []
    for step in plan:
        status = step.get("status", "pending")
        line = f"Step {step.get('id', '?')}: {step.get('description', '')} [status: {status}]"
        if step.get("result_preview"):
            line += f"\nRisultato: {step['result_preview']}"
        if step.get("error"):
            line += f"\nErrore: {step['error']}"
        plan_summary_lines.append(line)

    execution_text = "\n".join(execution_summaries)

    prompt = (
        "Hai completato i passaggi pianificati per l'utente."
        "\nRiassumi cosa hai fatto e fornisci la risposta finale in italiano, "
        "citando risultati dei tool quando rilevanti."
        "\n\nPiano eseguito:\n"
        f"{chr(10).join(plan_summary_lines)}"
        "\n\nDettagli esecuzione:\n"
        f"{execution_text if execution_text else 'Nessun dettaglio aggiuntivo.'}"
        "\n\nRichiesta originale:\n"
        f"{request.message}"
    )

    response = await ollama.generate_with_context(
        prompt=prompt,
        session_context=session_context,
        retrieved_memory=retrieved_memory if retrieved_memory else None,
        tools=None,
        tools_description=None,
    )
    if isinstance(response, dict):
        return response.get("content", "")
    return str(response)


async def execute_plan_steps(
    state: LangGraphChatState,
    plan: List[PlanStep],
    start_index: int,
) -> Dict[str, Any]:
    logger = logging.getLogger(__name__)

    session_id = state["session_id"]
    db = state["db"]
    
    # Get tenant_id from session
    from app.models.database import Session as SessionModel
    from sqlalchemy import select
    tenant_result = await db.execute(
        select(SessionModel.tenant_id).where(SessionModel.id == session_id)
    )
    tenant_id = tenant_result.scalar_one_or_none()
    
    tool_manager = ToolManager(db=db, tenant_id=tenant_id)

    execution_summaries: List[str] = []
    tool_results: List[Dict[str, Any]] = []
    tools_used: List[str] = []
    tool_details: List[ToolExecutionDetail] = []

    index = start_index
    acknowledgement = state.get("acknowledgement", False)
    waiting_for_user = False

    while index < len(plan):
        step = plan[index]
        action = step.get("action", "tool")

        if step.get("status") == "complete":
            index += 1
            continue

        if action == "wait_user":
            if acknowledgement and step.get("status") == "waiting":
                step["status"] = "complete"
                index += 1
                continue
            if acknowledgement and step.get("status") != "waiting":
                step["status"] = "complete"
                index += 1
                continue
            step["status"] = "waiting"
            waiting_for_user = True
            break

        if action == "respond":
            step["status"] = "complete"
            index += 1
            break

        tool_name = step.get("tool")
        if not tool_name:
            step["status"] = "complete"
            index += 1
            continue

        try:
            logger.info("Executing planned tool %s", tool_name)
            # Get current_user from state
            current_user = state.get("current_user")
            result = await tool_manager.execute_tool(
                tool_name,
                step.get("inputs", {}),
                db=db,
                session_id=session_id,
                current_user=current_user,
            )
            step["status"] = "complete"
            preview = json.dumps(result, ensure_ascii=False)[:500]
            step["result_preview"] = preview
            execution_summaries.append(f"Tool {tool_name}: {preview}")
            tool_results.append({"tool": tool_name, "parameters": step.get("inputs", {}), "result": result})
            tools_used.append(tool_name)
            success = True
            error = None
            if isinstance(result, dict):
                if result.get("error"):
                    success = False
                    error = result.get("error")
            tool_details.append(
                ToolExecutionDetail(
                    tool_name=tool_name,
                    parameters=step.get("inputs", {}),
                    result=result if isinstance(result, dict) else {"output": result},
                    success=success,
                    error=error,
                )
            )
        except Exception as exc:  # pragma: no cover - tool failure
            logger.warning("Planned tool %s failed: %s", tool_name, exc, exc_info=True)
            step["status"] = "error"
            step["error"] = str(exc)
            execution_summaries.append(f"Tool {tool_name} errore: {exc}")
            tool_details.append(
                ToolExecutionDetail(
                    tool_name=tool_name,
                    parameters=step.get("inputs", {}),
                    result={"error": str(exc)},
                    success=False,
                    error=str(exc),
                )
            )
        index += 1

    return {
        "plan": plan,
        "next_index": index,
        "waiting_for_user": waiting_for_user,
        "execution_summaries": execution_summaries,
        "tool_results": tool_results,
        "tools_used": tools_used,
        "tool_details": tool_details,
    }


class LangGraphChatState(TypedDict, total=False):
    event: Dict[str, Any]
    session_id: UUID
    request: ChatRequest
    db: AsyncSession
    ollama: OllamaClient
    planner_client: OllamaClient
    memory_manager: MemoryManager
    session_context: List[Dict[str, str]]
    retrieved_memory: List[str]
    memory_used: Dict[str, Any]
    messages: List[Dict[str, str]]
    tool_calls: List[Dict[str, Any]]
    tool_results: List[Dict[str, Any]]
    notifications: List[Dict[str, Any]]
    high_urgency_notifications: List[Dict[str, Any]]
    notification_center: NotificationCenter
    previous_messages: List[Dict[str, str]]
    acknowledgement: bool
    plan: List[PlanStep]
    plan_index: int
    plan_dirty: bool
    plan_completed: bool
    plan_origin: Optional[str]
    routing_decision: str
    response: Optional[str]
    chat_response: Optional[ChatResponse]
    assistant_message_saved: bool
    done: bool
    agent_activity: List[Dict[str, Any]]
    agent_activity_manager: AgentActivityStream
    task_queue: TaskQueue
    current_task: Optional[Task]


async def event_handler_node(state: LangGraphChatState) -> LangGraphChatState:
    """Normalizza l'evento in arrivo e aggiorna la history."""
    logger = logging.getLogger(__name__)
    logger.error("📥📥📥 Event Handler node executing - CRITICAL LOG")
    logger.info("📥 Event Handler node executing")
    log_agent_activity(state, agent_id="event_handler", status="started")
    try:
        messages = state.get("messages", [])
        event = state.get("event", {})
        role = event.get("role", "user")
        content = event.get("content", "")
        messages.append({"role": role, "content": content})
        state["messages"] = messages
        logger.error("✅✅✅ Event Handler completed, returning state - CRITICAL LOG")
        log_agent_activity(state, agent_id="event_handler", status="completed")
        return state
    except Exception as exc:
        logger.error("❌❌❌ Event Handler ERROR: %s", exc, exc_info=True)
        log_agent_activity(
            state,
            agent_id="event_handler",
            status="error",
            message=str(exc),
        )
        raise


async def orchestrator_node(state: LangGraphChatState) -> LangGraphChatState:
    """Per ora instrada sempre verso il main agent."""
    logger = logging.getLogger(__name__)
    logger.error("🎯🎯🎯 Orchestrator node executing - CRITICAL LOG")
    logger.info("🎯 Orchestrator node executing")
    log_agent_activity(state, agent_id="orchestrator", status="started")
    try:
        state["routing_decision"] = "tool_loop"
        logger.error("✅✅✅ Orchestrator completed, routing to tool_loop - CRITICAL LOG")
        logger.info("✅ Orchestrator completed, routing to tool_loop")
        log_agent_activity(state, agent_id="orchestrator", status="completed")
        return state
    except Exception as exc:
        logger.error("❌❌❌ Orchestrator ERROR: %s", exc, exc_info=True)
        log_agent_activity(
            state,
            agent_id="orchestrator",
            status="error",
            message=str(exc),
        )
        raise


async def tool_loop_node(state: LangGraphChatState) -> LangGraphChatState:
    """Gestisce pianificazione, esecuzione tool e fallback legacy."""
    logger = logging.getLogger(__name__)
    logger.info("🔧 Tool Loop node executing")
    log_agent_activity(state, agent_id="tool_loop", status="started")
    request = state["request"]
    acknowledgement = state.get("acknowledgement", False)

    try:
        plan = state.get("plan", []) or []
        plan_index = state.get("plan_index", 0)
        state.setdefault("plan_dirty", False)
        state.setdefault("plan_completed", not plan)
        state.setdefault("assistant_message_saved", False)

        task_queue: Optional[TaskQueue] = state.get("task_queue")
        session_id = state.get("session_id")
        active_task: Optional[Task] = state.get("current_task")

        # Check if this is an auto-task message (from dispatcher)
        is_auto_task = request.message.startswith("[auto-task]")
        
        # If it's an auto-task, prioritize task processing over normal planning
        if is_auto_task and task_queue and session_id:
            # Try to get the next task from queue
            if not active_task:
                next_task = task_queue.start_next(session_id)
                if next_task:
                    active_task = next_task
                    state["current_task"] = active_task
                    log_agent_activity(
                        state,
                        agent_id="task_dispatcher",
                        status="started",
                        message=f"Auto-task: gestione {active_task.type}",
                    )

        # Get tenant_id from session
        db = state["db"]
        if session_id:
            from app.models.database import Session as SessionModel
            from sqlalchemy import select
            tenant_result = await db.execute(
                select(SessionModel.tenant_id).where(SessionModel.id == session_id)
            )
            tenant_id = tenant_result.scalar_one_or_none()
        else:
            tenant_id = None

        tool_manager = ToolManager(db=db, tenant_id=tenant_id)
        current_user = state.get("current_user")
        available_tools = await tool_manager.get_available_tools(current_user=current_user)
        available_tool_names = [tool.get("name") for tool in available_tools if tool.get("name")]

        if task_queue and session_id:
            if active_task:
                refreshed = task_queue.get_task(session_id, active_task.id)
                if refreshed:
                    active_task = refreshed
                else:
                    active_task = None
                    state["current_task"] = None

            if active_task is None:
                waiting = task_queue.find_task_by_status(
                    session_id, TaskStatus.WAITING_USER
                )
                if waiting:
                    active_task = waiting
                    state["current_task"] = active_task

            if active_task is None:
                next_task = task_queue.start_next(session_id)
                if next_task:
                    active_task = next_task
                    state["current_task"] = active_task
                    log_agent_activity(
                        state,
                        agent_id="task_dispatcher",
                        status="started",
                        message=f"Gestione task {active_task.type}",
                    )

            if active_task:
                handled = _handle_active_task(state, active_task, task_queue)
                if handled:
                    handled_state, loop_status = handled
                    log_agent_activity(state, agent_id="tool_loop", status=loop_status)
                    return handled_state

        # Se non abbiamo un piano corrente e il messaggio non è solo conferma, valutiamo la necessità di un piano
        # IMPORTANTE: Non chiamare il planner se il messaggio è vuoto o è un messaggio automatico senza contenuto reale
        message_content = request.message.strip()
        is_auto_task = message_content.startswith("[auto-task]")
        should_plan = not plan and not acknowledgement and message_content and not is_auto_task
        
        if should_plan:
            planner_client = state.get("planner_client") or state["ollama"]
            log_agent_activity(state, agent_id="planner", status="started")
            try:
                logger.info(f"🔍 Planning for message: {request.message[:100]}")
                logger.info(f"   Message length: {len(message_content)}, is_auto_task: {is_auto_task}, acknowledgement: {acknowledgement}")
                analysis = await analyze_message_for_plan(
                    planner_client,
                    request,
                    available_tools,
                    state.get("session_context", []),
                    ollama_client=state.get("ollama"),
                )
                logger.info(f"📋 Planner analysis: needs_plan={analysis.get('needs_plan')}, reason={analysis.get('reason')}, steps_count={len(analysis.get('steps', []))}")
                if analysis.get("steps"):
                    for idx, step in enumerate(analysis.get("steps", [])):
                        logger.info(f"  Step {idx}: action={step.get('action')}, tool={step.get('tool')}, inputs={step.get('inputs')}")
            except Exception as exc:
                logger.error(f"❌ Planner error: {exc}", exc_info=True)
                log_agent_activity(
                    state,
                    agent_id="planner",
                    status="error",
                    message=str(exc),
                )
                raise
            else:
                log_agent_activity(state, agent_id="planner", status="completed")
            state["plan_analysis"] = analysis  # utile per debugging/test
            log_planning_status(
                state,
                status="analysis",
                reason=str(analysis.get("reason", "")),
                plan=normalize_plan_steps(analysis.get("steps", []), available_tool_names),
            )

            if analysis.get("needs_plan") and analysis.get("steps"):
                plan = normalize_plan_steps(analysis.get("steps", []), available_tool_names)
                if plan:
                    logger.info(f"✅ Generated plan with {len(plan)} steps")
                    state["plan"] = plan
                    state["plan_index"] = 0
                    state["plan_dirty"] = True
                    state["plan_completed"] = False
                    state["plan_origin"] = request.message
                    log_planning_status(
                        state,
                        status="generated",
                        reason=str(analysis.get("reason", "")),
                        plan=plan,
                    )
                else:
                    logger.warning("⚠️  Plan analysis returned no valid steps after normalization")
            else:
                logger.info(f"ℹ️  Planner returned needs_plan={analysis.get('needs_plan')}, steps={len(analysis.get('steps', []))} - will generate direct response")
        else:
            logger.info(f"⏭️  Skipping planner: plan={bool(plan)}, acknowledgement={acknowledgement}, message_content='{message_content[:50]}...', is_auto_task={is_auto_task}")

        # Esegui piano se presente
        if plan:
            logger.error(f"🔍🔍🔍 Executing plan with {len(plan)} steps, acknowledgement={acknowledgement}, plan_index={state.get('plan_index', 0)}")
            execution = await execute_plan_steps(state, plan, state.get("plan_index", 0))
            state["plan"] = execution["plan"]
            state["plan_index"] = execution["next_index"]
            state["plan_dirty"] = True

            # Accumula risultati tool
            if execution["tool_results"]:
                state.setdefault("tool_results", []).extend(execution["tool_results"])

            waiting = execution["waiting_for_user"]
            remaining_steps = any(
                step.get("status") not in {"complete", "waiting"}
                for step in execution["plan"]
            )
            
            logger.error(f"🔍🔍🔍 Plan execution: waiting={waiting}, remaining_steps={remaining_steps}, tool_results={len(execution['tool_results'])}, execution_summaries={len(execution.get('execution_summaries', []))}")

            if waiting:
                waiting_step = execution["plan"][max(0, min(state["plan_index"], len(execution["plan"]) - 1))]
                response_text = waiting_step.get("description", "Dimmi come procedere.")
                state["response"] = response_text
                log_planning_status(
                    state,
                    status="waiting_confirmation",
                    plan=execution["plan"],
                    extra={"message": response_text},
                )
                log_agent_activity(
                    state,
                    agent_id="tool_loop",
                    status="waiting",
                    message=response_text,
                )
                _snapshot_notifications(state)
                notifications = state.get("notifications", [])
                high_priority_notifications = state.get("high_urgency_notifications", [])
                state["chat_response"] = ChatResponse(
                    response=response_text,
                    session_id=state["session_id"],
                    memory_used=state.get("memory_used", {}),
                    tools_used=[tr["tool"] for tr in execution["tool_results"]],
                    tool_details=execution["tool_details"],
                    notifications_count=len(notifications),
                    high_urgency_notifications=high_priority_notifications,
                    agent_activity=state.get("agent_activity", []),
                )
                state["plan_completed"] = False
                state["assistant_message_saved"] = False
                return state

            # Piano eseguito (o nessun ulteriore step)
            # IMPORTANTE: Anche se non ci sono tool_results, generiamo comunque una risposta
            # se il piano è completato (specialmente dopo un acknowledgement)
            execution_summaries = execution.get("execution_summaries", [])
            if not execution_summaries and not execution["tool_results"]:
                # Piano completato senza tool_results (tutti gli step erano già completati)
                # Genera una risposta basata sul piano stesso
                logger.error(f"🔍🔍🔍 Plan completed without tool_results, generating response from plan steps")
                completed_steps = [s for s in execution["plan"] if s.get("status") == "complete"]
                if completed_steps:
                    # Usa la descrizione dell'ultimo step completato o genera una risposta generica
                    last_step = completed_steps[-1]
                    if last_step.get("action") == "respond":
                        final_text = last_step.get("description", "Ho completato le azioni richieste.")
                    else:
                        final_text = f"Ho completato: {last_step.get('description', 'le azioni richieste')}."
                else:
                    final_text = "Ho completato le azioni richieste."
            else:
                final_text = await summarize_plan_results(
                    state["ollama"],
                    request,
                    state.get("session_context", []),
                    state.get("retrieved_memory", []),
                    execution["plan"],
                    execution_summaries,
                )

            logger.error(f"🔍🔍🔍 Final response generated: {len(final_text) if final_text else 0} characters")
            state["response"] = final_text
            log_planning_status(
                state,
                status="completed" if not remaining_steps else "partial",
                plan=execution["plan"],
                extra={
                    "summary": final_text,
                    "tools_used": execution["tools_used"],
                },
            )
            _snapshot_notifications(state)
            notifications = state.get("notifications", [])
            high_priority_notifications = state.get("high_urgency_notifications", [])
            state["chat_response"] = ChatResponse(
                response=final_text,
                session_id=state["session_id"],
                memory_used=state.get("memory_used", {}),
                tools_used=execution["tools_used"],
                tool_details=execution["tool_details"],
                notifications_count=len(notifications),
                high_urgency_notifications=high_priority_notifications,
                agent_activity=state.get("agent_activity", []),
            )
            state["plan_completed"] = not remaining_steps
            state["assistant_message_saved"] = False
            log_agent_activity(state, agent_id="tool_loop", status="completed")
            return state

        # No plan - generate direct response using Ollama (but continue through graph nodes)
        logger.info("📝 No plan needed - generating direct response, graph will continue")
        
        # Get tenant_id from session
        from app.models.database import Session as SessionModel
        from sqlalchemy import select
        tenant_result = await state["db"].execute(
            select(SessionModel.tenant_id).where(SessionModel.id == state["session_id"])
        )
        tenant_id = tenant_result.scalar_one_or_none()
        
        current_user = state.get("current_user")
        tool_manager = ToolManager(db=state["db"], tenant_id=tenant_id)
        available_tools = await tool_manager.get_available_tools(current_user=current_user)
        
        # Generate response using Ollama with tool calling capability
        # This allows Ollama to decide if it needs tools or can respond directly
        ollama = state["ollama"]
        session_context = state["session_context"]
        retrieved_memory = list(state["retrieved_memory"])
        
        # Use Ollama's native tool calling
        tools_description = await tool_manager.get_tools_system_prompt()
        
        try:
            response_data = await ollama.generate_with_context(
                prompt=request.message,
                session_context=session_context,
                retrieved_memory=retrieved_memory if retrieved_memory else None,
                tools=available_tools,
                tools_description=tools_description,
                return_raw=True,
            )
        except Exception as ollama_error:
            logger.error(f"❌ Ollama error in tool_loop_node: {ollama_error}", exc_info=True)
            log_agent_activity(
                state,
                agent_id="tool_loop",
                status="error",
                message=f"Ollama connection failed: {str(ollama_error)}",
            )
            # Return a fallback response so the graph can continue
            state["response"] = "Mi dispiace, ma al momento non posso rispondere perché il servizio di intelligenza artificiale non è disponibile. Verifica che Ollama sia in esecuzione."
            state["tools_used"] = []
            state.setdefault("tool_results", [])
            state["plan_completed"] = True
            state["assistant_message_saved"] = False
            log_agent_activity(state, agent_id="tool_loop", status="completed")
            return state
        
        # Extract response and tool calls
        response_text = ""
        tool_calls = []
        tools_used = []
        tool_results = []
        
        if isinstance(response_data, dict):
            response_text = response_data.get("content", "")
            parsed_tc = response_data.get("_parsed_tool_calls")
            if parsed_tc:
                tool_calls = parsed_tc
                logger.error(f"🔧🔧🔧 Using _parsed_tool_calls: {len(tool_calls)} call(s)")
            else:
                # Check multiple possible locations for tool_calls
                tool_calls_found = False
                tool_calls_raw = None
                
                # 1. Check for _raw_tool_calls (from generate_with_context)
                if "_raw_tool_calls" in response_data and response_data["_raw_tool_calls"]:
                    tool_calls_raw = response_data["_raw_tool_calls"]
                    tool_calls_found = True
                    logger.error(f"🔧🔧🔧 Found _raw_tool_calls: {len(tool_calls_raw)} call(s)")
                # 2. Check for tool_calls directly in response_data (OpenAI-style format)
                elif "tool_calls" in response_data:
                    tool_calls_raw = response_data["tool_calls"]
                    tool_calls_found = True
                    logger.error(f"🔧🔧🔧 Found tool_calls in response_data: {len(tool_calls_raw)} call(s)")
                # 3. Check in message.tool_calls (Ollama format when return_raw=True)
                elif "message" in response_data and isinstance(response_data["message"], dict) and "tool_calls" in response_data["message"]:
                    tool_calls_raw = response_data["message"]["tool_calls"]
                    tool_calls_found = True
                    logger.error(f"🔧🔧🔧 Found tool_calls in response_data.message: {len(tool_calls_raw)} call(s)")
                # 4. Check in raw_result.message.tool_calls (Ollama format)
                elif "raw_result" in response_data:
                    raw_result = response_data.get("raw_result", {})
                    message = raw_result.get("message")
                    if isinstance(message, dict) and "tool_calls" in message:
                        tool_calls_raw = message["tool_calls"]
                        tool_calls_found = True
                        logger.error(f"🔧🔧🔧 Found tool_calls in raw_result.message: {len(tool_calls_raw)} call(s)")
                
                if tool_calls_found and tool_calls_raw:
                    logger.error(f"🔧🔧🔧 Found tool_calls in response_data: {len(tool_calls_raw)} call(s)")
                    tool_calls = []
                    for tc in tool_calls_raw:
                        if isinstance(tc, dict):
                            # Handle OpenAI-style format: {"function": {"name": "...", "arguments": {...}}}
                            if "function" in tc:
                                func = tc.get("function", {})
                                tool_name = func.get("name")
                                arguments = func.get("arguments", {})
                                
                                # Parse arguments if it's a JSON string (OpenAI format)
                                if isinstance(arguments, str):
                                    try:
                                        arguments = json.loads(arguments)
                                    except (json.JSONDecodeError, TypeError):
                                        logger.warning(f"Failed to parse arguments as JSON for tool {tool_name}: {arguments}")
                                        arguments = {}
                                
                                tool_calls.append({
                                    "name": tool_name,
                                    "parameters": arguments if isinstance(arguments, dict) else {},
                                })
                            # Handle direct format: {"name": "...", "parameters": {...}}
                            elif "name" in tc:
                                tool_calls.append({
                                    "name": tc.get("name"),
                                    "parameters": tc.get("parameters", {}),
                                })
        else:
            response_text = response_data or ""
        
        # Execute tool calls if any
        if tool_calls:
            logger.error(f"🔧🔧🔧 Found {len(tool_calls)} tool call(s) to execute")
            for idx, tool_call in enumerate(tool_calls):
                tool_name = tool_call.get("name")
                tool_params = tool_call.get("parameters", {})
                logger.error(f"🔧🔧🔧 Executing tool {idx+1}/{len(tool_calls)}: {tool_name} with params: {tool_params}")
                if tool_name:
                    try:
                        result = await tool_manager.execute_tool(
                            tool_name, tool_params, state["db"], 
                            session_id=state["session_id"],
                            current_user=current_user
                        )
                        logger.error(f"✅✅✅ Tool {tool_name} executed successfully. Result type: {type(result)}, keys: {list(result.keys()) if isinstance(result, dict) else 'N/A'}")
                        tool_results.append({
                            "tool": tool_name,
                            "parameters": tool_params,
                            "result": result,
                        })
                        tools_used.append(tool_name)
                    except Exception as exc:
                        logger.error(f"❌❌❌ Errore eseguendo tool {tool_name}: {exc}", exc_info=True)
                        tool_results.append({
                            "tool": tool_name,
                            "parameters": tool_params,
                            "result": {"error": str(exc)},
                        })
            logger.error(f"🔧🔧🔧 Tool execution complete. Total results: {len(tool_results)}")
        else:
            logger.error(f"🔧🔧🔧 No tool calls found in response")
        
        # After all tool calls are executed, generate final response if we have tool results
        # IMPORTANT: Always generate a response after tool execution, even if response_text already exists
        if tool_results:
            logger.error(f"🔍🔍🔍 Tool results found: {len(tool_results)}. Generating final response...")
            tool_results_text = "\n\n=== Risultati Tool ===\n"
            for tr in tool_results:
                tool_name = tr.get('tool', 'unknown')
                tool_result = tr.get('result', {})
                tool_results_text += f"Tool: {tool_name}\n"
                if isinstance(tool_result, dict):
                    # Check for errors first
                    if "error" in tool_result:
                        tool_results_text += f"ERRORE: {tool_result['error']}\n\n"
                    else:
                        result_str = json.dumps(tool_result, indent=2, ensure_ascii=False, default=str)
                        tool_results_text += f"{result_str}\n\n"
                else:
                    result_str = str(tool_result)
                    tool_results_text += f"{result_str}\n\n"
            
            logger.error(f"🔍🔍🔍 Tool results text length: {len(tool_results_text)}")
            
            # Use existing response_text as context if available, otherwise use the original request
            context_text = response_text if response_text else request.message
            final_prompt = f"""{context_text}

{tool_results_text}

Rispondi all'utente basandoti sui risultati dei tool sopra."""
            try:
                logger.error(f"🔍🔍🔍 Calling Ollama to generate final response. Prompt length: {len(final_prompt)}")
                # IMPORTANT: When tools=None, generate_with_context returns a string, not a dict
                # So we don't need return_raw=True here
                final_response = await ollama.generate_with_context(
                    prompt=final_prompt,
                    session_context=session_context,
                    retrieved_memory=retrieved_memory if retrieved_memory else None,
                    tools=None,  # No tools - force text response
                    tools_description=None,
                    return_raw=False,  # Return string, not dict
                )
                logger.error(f"🔍🔍🔍 Ollama response type: {type(final_response)}")
                # When return_raw=False, generate_with_context returns a string
                if isinstance(final_response, str):
                    # Check if the string is actually JSON (Ollama sometimes returns JSON even with tools=None)
                    response_text = final_response
                    # Try to parse as JSON to extract content if it's a JSON string
                    try:
                        parsed_json = json.loads(final_response)
                        if isinstance(parsed_json, dict):
                            # Extract content from JSON structure
                            if "content" in parsed_json:
                                response_text = parsed_json["content"]
                            elif "message" in parsed_json and isinstance(parsed_json["message"], dict):
                                response_text = parsed_json["message"].get("content", "")
                            elif "message" in parsed_json and isinstance(parsed_json["message"], str):
                                response_text = parsed_json["message"]
                            # If it still has tool_calls, ignore them and use content or empty string
                            if "tool_calls" in parsed_json and not response_text:
                                logger.warning("⚠️  Response contains tool_calls but no content - ignoring tool_calls")
                                response_text = ""
                    except (json.JSONDecodeError, TypeError):
                        # Not JSON, use as-is
                        pass
                    logger.error(f"🔍🔍🔍 String response length: {len(response_text)}")
                elif isinstance(final_response, dict):
                    # Fallback: if it's a dict, extract content
                    content = final_response.get("content", "")
                    if not content:
                        raw_result = final_response.get("raw_result", {})
                        if isinstance(raw_result, dict):
                            message = raw_result.get("message", {})
                            if isinstance(message, dict):
                                content = message.get("content", "")
                            elif isinstance(message, str):
                                content = message
                    response_text = content
                    logger.error(f"🔍🔍🔍 Extracted content from dict, length: {len(response_text)}")
                    if not response_text:
                        logger.error(f"🔍🔍🔍 Full response structure: {list(final_response.keys())}")
                else:
                    response_text = str(final_response) or ""
                    logger.error(f"🔍🔍🔍 Converted to string, length: {len(response_text)}")
                
                if not response_text:
                    logger.error("⚠️⚠️⚠️  Final response is EMPTY, using fallback")
                    # Create a more detailed fallback
                    fallback_parts = []
                    for tr in tool_results:
                        tool_name = tr.get('tool', 'unknown')
                        tool_result = tr.get('result', {})
                        if isinstance(tool_result, dict) and "error" in tool_result:
                            fallback_parts.append(f"Tool {tool_name}: ERRORE - {tool_result['error']}")
                        else:
                            fallback_parts.append(f"Tool {tool_name}: Eseguito con successo")
                    response_text = f"Ho eseguito {len(tool_results)} tool(s). " + "; ".join(fallback_parts)
                else:
                    logger.error(f"✅✅✅ Generated final response: {len(response_text)} characters. Preview: {response_text[:200]}")
            except Exception as final_error:
                logger.error(f"❌❌❌ Error generating final response: {final_error}", exc_info=True)
                # Use a simple summary of tool results as fallback
                response_text = f"Ho eseguito {len(tool_results)} tool(s). Risultati: {json.dumps(tool_results, indent=2, ensure_ascii=False, default=str)[:500]}"
        
        # Store response in state (will be finalized by response_formatter_node)
        # DO NOT create chat_response here - let response_formatter_node do it
        logger.error(f"🔍 Tool Loop: Storing response in state. Length: {len(response_text) if response_text else 0}")
        logger.error(f"🔍 Tool Loop: Response preview: {response_text[:200] if response_text else 'EMPTY'}")
        logger.error(f"🔍 Tool Loop: tools_used: {len(tools_used)}, tool_results: {len(tool_results)}")
        state["response"] = response_text
        state["tools_used"] = tools_used
        state.setdefault("tool_results", [])
        state["tool_results"].extend(tool_results)
        state["plan_completed"] = True
        state["assistant_message_saved"] = False  # Will be saved by response_formatter_node
        
        # Update memory_used if needed
        if not state.get("memory_used"):
            state["memory_used"] = {}
        
        log_agent_activity(state, agent_id="tool_loop", status="completed")
        # Continue to next node (knowledge_agent) - don't return early
        return state
    except Exception as exc:
        log_agent_activity(
            state,
            agent_id="tool_loop",
            status="error",
            message=str(exc),
        )
        raise


async def knowledge_agent_node(state: LangGraphChatState) -> LangGraphChatState:
    """Aggiorna la memoria breve e avvia auto-learning in background se necessario."""
    logger = logging.getLogger(__name__)
    logger.info("🧠 Knowledge Agent node executing")
    log_agent_activity(state, agent_id="knowledge_agent", status="started")
    try:
        request = state["request"]
        if not request.use_memory:
            log_agent_activity(state, agent_id="knowledge_agent", status="completed")
            return state

        memory_manager = state.get("memory_manager")
        if memory_manager is None:
            log_agent_activity(state, agent_id="knowledge_agent", status="completed")
            return state

        response_text = state.get("response")
        if not response_text:
            chat_response = state.get("chat_response")
            if chat_response:
                response_text = chat_response.response

        if not response_text:
            log_agent_activity(state, agent_id="knowledge_agent", status="completed")
            return state

        logger = logging.getLogger(__name__)

        # Update short-term memory with the latest exchange
        try:
            new_context = {
                "last_user_message": request.message,
                "last_assistant_message": response_text,
                "message_count": len(state.get("previous_messages", [])) + 2,
            }
            # Get tenant_id from session
            from app.models.database import Session as SessionModel
            from sqlalchemy import select
            tenant_result = await state["db"].execute(
                select(SessionModel.tenant_id).where(SessionModel.id == state["session_id"])
            )
            tenant_id = tenant_result.scalar_one_or_none()
            await memory_manager.update_short_term_memory(
                state["db"],
                state["session_id"],
                new_context,
                tenant_id=tenant_id,
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
            logger.info(
                "⏭️ Skip auto-learning: conversazione insufficiente (%s messaggi)",
                len(recent_messages),
            )
            log_agent_activity(state, agent_id="knowledge_agent", status="completed")
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
                            logger.info(
                                "✅ Auto-learning completato: %s elementi indicizzati",
                                stats.get("indexed", 0),
                            )
                        else:
                            logger.info(
                                "ℹ️ Nessuna conoscenza estratta (soglia importanza non superata)"
                            )
                    except Exception:
                        logger.warning("Errore nell'auto-learning in background", exc_info=True)

            asyncio.create_task(_extract_knowledge_background())
        except Exception:
            logger.warning("Impossibile avviare auto-learning", exc_info=True)
    except Exception as exc:
        log_agent_activity(
            state,
            agent_id="knowledge_agent",
            status="error",
            message=str(exc),
        )
        raise

    log_agent_activity(state, agent_id="knowledge_agent", status="completed")
    return state


async def notification_collector_node(state: LangGraphChatState) -> LangGraphChatState:
    """Aggrega le notifiche raccolte dagli agenti specializzati."""
    logger = logging.getLogger(__name__)
    logger.info("🔔 Notification Collector node executing")
    log_agent_activity(state, agent_id="notification_collector", status="started")
    try:
        _snapshot_notifications(state)
        log_agent_activity(state, agent_id="notification_collector", status="completed")
        return state
    except Exception as exc:
        log_agent_activity(
            state,
            agent_id="notification_collector",
            status="error",
            message=str(exc),
        )
        raise


async def response_formatter_node(state: LangGraphChatState) -> LangGraphChatState:
    """Garantisce che un ChatResponse sia presente nello stato finale."""
    logger = logging.getLogger(__name__)
    logger.info("📝 Response Formatter node executing")
    log_agent_activity(state, agent_id="response_formatter", status="started")
    try:
        if "chat_response" not in state or state["chat_response"] is None:
            _snapshot_notifications(state)
            notifications = state.get("notifications", [])
            high_priority_notifications = state.get("high_urgency_notifications", [])
            
            # Extract tools_used and tool_details from state
            tools_used = state.get("tools_used", [])
            tool_results = state.get("tool_results", [])
            
            # Convert tool_results to ToolExecutionDetail format
            from app.models.schemas import ToolExecutionDetail
            tool_details = [
                ToolExecutionDetail(
                    tool_name=tr.get("tool", ""),
                    parameters=tr.get("parameters", {}),
                    result=tr.get("result", {}),
                    success=not isinstance(tr.get("result"), dict) or "error" not in tr.get("result", {}),
                )
                for tr in tool_results
            ]
            
            response_text = state.get("response", "")
            logger.error(f"🔍 Response Formatter: response text length: {len(response_text) if response_text else 0}")
            logger.error(f"🔍 Response Formatter: response preview: {response_text[:100] if response_text else 'EMPTY'}")
            logger.error(f"🔍 Response Formatter: tools_used: {len(tools_used)}, tool_results: {len(tool_results)}")
            
            state["chat_response"] = ChatResponse(
                response=response_text,
                session_id=state["session_id"],
                memory_used=state.get("memory_used", {}),
                tools_used=tools_used,
                tool_details=tool_details,
                notifications_count=len(notifications),
                high_urgency_notifications=high_priority_notifications,
                agent_activity=state.get("agent_activity", []),
            )
        else:
            state["chat_response"] = state["chat_response"].model_copy(
                update={"agent_activity": state.get("agent_activity", [])}
            )
        log_agent_activity(state, agent_id="response_formatter", status="completed")
        return state
    except Exception as exc:
        log_agent_activity(
            state,
            agent_id="response_formatter",
            status="error",
            message=str(exc),
        )
        raise


def _routing_router(state: LangGraphChatState) -> str:
    return "tool_loop"


def build_langgraph_app() -> StateGraph:
    graph = StateGraph(LangGraphChatState)
    graph.add_node("event_handler", event_handler_node)
    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("tool_loop", tool_loop_node)
    graph.add_node("knowledge_agent", knowledge_agent_node)
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
    graph.add_edge("knowledge_agent", "notification_collector")
    graph.add_edge("notification_collector", "response_formatter")
    graph.add_edge("response_formatter", END)
    return graph.compile()


async def run_langgraph_chat(
    *,
    db: AsyncSession,
    session_id: UUID,
    request: ChatRequest,
    ollama: OllamaClient,
    planner_client: OllamaClient,
    agent_activity_stream: AgentActivityStream,
    memory_manager: MemoryManager,
    session_context: List[Dict[str, str]],
    retrieved_memory: List[str],
    memory_used: Dict[str, Any],
    previous_messages: Optional[List[Dict[str, str]]] = None,
    pending_plan: Optional[Dict[str, Any]] = None,
    current_user: Optional[Any] = None,  # User model for tool filtering
) -> LangGraphResult:
    app = build_langgraph_app()
    acknowledgement = is_acknowledgement(request.message)
    plan_steps = []
    plan_index = 0
    if pending_plan:
        plan_steps = pending_plan.get("steps", [])
        plan_index = pending_plan.get("current_step", 0)
    state: LangGraphChatState = {
        "event": {"role": "user", "content": request.message},
        "session_id": session_id,
        "request": request,
        "db": db,
        "ollama": ollama,
        "planner_client": planner_client,
        "memory_manager": memory_manager,
        "session_context": session_context,
        "retrieved_memory": retrieved_memory,
        "memory_used": memory_used,
        "messages": [],
        "tool_calls": [],
        "tool_results": [],
        "notifications": [],
        "high_urgency_notifications": [],
        "notification_center": NotificationCenter(),
        "previous_messages": previous_messages or [],
        "acknowledgement": acknowledgement,
        "plan": plan_steps,
        "plan_index": plan_index,
        "plan_dirty": False,
        "plan_completed": not plan_steps,
        "assistant_message_saved": False,
        "done": False,
        "agent_activity": [],
        "agent_activity_manager": agent_activity_stream,
        "task_queue": get_task_queue(),
        "current_task": None,
        "current_user": current_user,  # Store current_user for tool filtering
    }
    logger = logging.getLogger(__name__)
    logger.error("🚀🚀🚀 Starting LangGraph execution for session %s - CRITICAL LOG", session_id)
    logger.info("🚀 Starting LangGraph execution for session %s", session_id)
    
    # Log initial state
    logger.info("   Initial state keys: %s", list(state.keys()))
    logger.info("   Event: %s", state.get("event", {}).get("content", "N/A")[:100])
    
    logger.error("🔍🔍🔍 About to invoke LangGraph app.ainvoke() - CRITICAL LOG")
    try:
        final_state = await app.ainvoke(state)
        logger.error("✅✅✅ LangGraph app.ainvoke() completed successfully - CRITICAL LOG")
    except Exception as exc:
        logger.error("❌❌❌ LangGraph app.ainvoke() FAILED: %s", exc, exc_info=True)
        raise
    
    # Log final state
    agent_activity = final_state.get("agent_activity", [])
    logger.info("✅ LangGraph execution completed. Agent activity events: %d", len(agent_activity))
    if agent_activity:
        # agent_activity contains dicts, not Pydantic models
        agent_ids = [e.get("agent_id") if isinstance(e, dict) else getattr(e, "agent_id", "unknown") for e in agent_activity]
        logger.info("   Agents that logged activity: %s", set(agent_ids))
    
    chat_response = final_state["chat_response"]

    plan_metadata: Optional[Dict[str, Any]] = None
    if final_state.get("plan_dirty"):
        plan_list = final_state.get("plan", []) or []
        if plan_list and not final_state.get("plan_completed"):
            plan_metadata = {
                "steps": plan_list,
                "current_step": final_state.get("plan_index", 0),
                "origin": final_state.get("plan_origin"),
            }
        else:
            plan_metadata = None
    elif pending_plan and not final_state.get("plan_completed"):
        plan_metadata = pending_plan

    return LangGraphResult(
        chat_response=chat_response,
        plan_metadata=plan_metadata,
        assistant_message_saved=final_state.get("assistant_message_saved", False),
    )

