from __future__ import annotations

import asyncio
import json
import logging
import re
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
from app.services.notification_center import NotificationCenter


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
    planner_client: OllamaClient,
    request: ChatRequest,
    available_tools: List[Dict[str, Any]],
    session_context: List[Dict[str, str]],
) -> Dict[str, Any]:
    tool_catalog = build_tool_catalog(available_tools)
    analysis_prompt = (
        "Analizza la richiesta dell'utente e valuta se per soddisfarla servono più azioni coordinate."\
        " Hai questi tool disponibili (studia attentamente le loro descrizioni e scegli SEMPRE quelli più pertinenti al compito):\n"
        f"{tool_catalog if tool_catalog else '- Nessun tool disponibile'}\n\n"
        "Linee guida obbligatorie:\n"
        "1. Se per rispondere devi consultare dati da integrazioni (email, calendario, file, ecc.), questo richiede un piano multi-step e l'uso esplicito del relativo tool.\n"
        "2. Preferisci tool specialistici alle ricerche generiche: usa web_search solo quando l'informazione richiesta arriva dal web pubblico o non esistono tool dedicati.\n"
        "3. Quando accedi a dati sensibili (email, calendario, file personali) includi uno step \"wait_user\" per richiedere conferma esplicita prima di eseguire il tool.\n"
        "4. Ogni piano deve descrivere in modo chiaro gli step successivi (max 5) con \"action\" tra tool/respond/wait_user, il tool da chiamare e i parametri essenziali.\n"
        "5. Se puoi rispondere immediatamente senza strumenti esterni, imposta needs_plan=false e steps=[].\n\n"
        "Rispondi SEMPRE con JSON valido, senza testo extra:\n"
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
        "Sei un pianificatore strategico. Identifica quando la richiesta richiede l'uso di strumenti o conferme, quindi produci un piano strutturato che li orchestria."\
        " Se una risposta diretta è sufficiente, restituisci needs_plan=false. In caso contrario, needs_plan=true e steps deve includere almeno un'azione tool seguita da una risposta finale."
    )

    try:
        client = planner_client
        response = await client.generate(
            prompt=analysis_prompt + f"\n\nRichiesta utente:\n{request.message}",
            context=session_context[-3:] if session_context else None,
            system=system_prompt,
        )
        content = response.get("message", {}).get("content", "")
        parsed = safe_json_loads(content)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        logging.getLogger(__name__).warning("Planner analysis failed", exc_info=True)

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

    tool_manager = ToolManager(db=state["db"])
    session_id = state["session_id"]
    db = state["db"]

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
            result = await tool_manager.execute_tool(
                tool_name,
                step.get("inputs", {}),
                db=db,
                session_id=session_id,
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
    """Gestisce pianificazione, esecuzione tool e fallback legacy."""

    logger = logging.getLogger(__name__)
    request = state["request"]
    acknowledgement = state.get("acknowledgement", False)

    plan = state.get("plan", []) or []
    plan_index = state.get("plan_index", 0)
    state.setdefault("plan_dirty", False)
    state.setdefault("plan_completed", not plan)
    state.setdefault("assistant_message_saved", False)

    tool_manager = ToolManager(db=state["db"])
    available_tools = await tool_manager.get_available_tools()
    available_tool_names = [tool.get("name") for tool in available_tools if tool.get("name")]

    # Se non abbiamo un piano corrente e il messaggio non è solo conferma, valutiamo la necessità di un piano
    if not plan and not acknowledgement:
        planner_client = state.get("planner_client") or state["ollama"]
        analysis = await analyze_message_for_plan(
            planner_client,
            request,
            available_tools,
            state.get("session_context", []),
        )
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
                logger.info("Generated plan with %s steps", len(plan))
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
                logger.info("Plan analysis returned no valid steps")

    # Esegui piano se presente
    if plan:
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
            )
            state["plan_completed"] = False
            state["assistant_message_saved"] = False
            return state

        # Piano eseguito (o nessun ulteriore step)
        final_text = await summarize_plan_results(
            state["ollama"],
            request,
            state.get("session_context", []),
            state.get("retrieved_memory", []),
            execution["plan"],
            execution["execution_summaries"],
        )

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
        )
        state["plan_completed"] = not remaining_steps
        state["assistant_message_saved"] = False
        return state

    # Fallback legacy pipeline con heuristica per web search
    force_web = should_force_web_search(request, acknowledgement)
    effective_request = request
    if force_web != request.force_web_search:
        effective_request = request.model_copy(update={"force_web_search": force_web})

    chat_response = await run_main_agent_pipeline(
        db=state["db"],
        session_id=state["session_id"],
        request=effective_request,
        ollama=state["ollama"],
        session_context=state["session_context"],
        retrieved_memory=list(state["retrieved_memory"]),
        memory_used=state["memory_used"],
    )
    state["chat_response"] = chat_response
    state["response"] = chat_response.response
    state["plan_completed"] = True
    state["assistant_message_saved"] = True
    state.setdefault("tool_results", [])
    if chat_response.tool_details:
        for detail in chat_response.tool_details:
            state["tool_results"].append(
                {
                    "tool": detail.tool_name,
                    "parameters": detail.parameters,
                    "result": detail.result,
                }
            )
    _snapshot_notifications(state)
    if acknowledgement and plan:
        log_planning_status(
            state,
            status="acknowledged_no_plan",
            plan=plan,
        )
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
    """Aggrega le notifiche raccolte dagli agenti specializzati."""

    _snapshot_notifications(state)
    return state


async def response_formatter_node(state: LangGraphChatState) -> LangGraphChatState:
    """Garantisce che un ChatResponse sia presente nello stato finale."""

    if "chat_response" not in state or state["chat_response"] is None:
        _snapshot_notifications(state)
        notifications = state.get("notifications", [])
        high_priority_notifications = state.get("high_urgency_notifications", [])
        state["chat_response"] = ChatResponse(
            response=state.get("response", ""),
            session_id=state["session_id"],
            memory_used=state.get("memory_used", {}),
            tools_used=[],
            tool_details=[],
            notifications_count=len(notifications),
            high_urgency_notifications=high_priority_notifications,
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
    planner_client: OllamaClient,
    memory_manager: MemoryManager,
    session_context: List[Dict[str, str]],
    retrieved_memory: List[str],
    memory_used: Dict[str, Any],
    previous_messages: Optional[List[Dict[str, str]]] = None,
    pending_plan: Optional[Dict[str, Any]] = None,
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
    }
    final_state = await app.ainvoke(state)
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

