from __future__ import annotations

import json as json_lib
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ollama_client import OllamaClient
from app.core.tool_manager import ToolManager
from app.models.database import Message as MessageModel
from app.models.schemas import ChatRequest, ChatResponse, ToolExecutionDetail
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


async def run_main_agent_pipeline(
    *,
    db: AsyncSession,
    session_id: UUID,
    request: ChatRequest,
    ollama: OllamaClient,
    session_context: List[Dict[str, str]],
    retrieved_memory: List[str],
    memory_used: Dict[str, Any],
    tenant_id: Optional[UUID] = None,
) -> ChatResponse:
    """
    Esegue l'attuale pipeline principale (tool calling + generazione risposta) e
    restituisce un oggetto ChatResponse.

    Questo metodo è condiviso sia dal percorso legacy (endpoint /chat) sia dai
    nodi LangGraph, in modo da evitare duplicazione della logica.
    """

    tool_manager = ToolManager(db=db, tenant_id=tenant_id)
    available_tools = await tool_manager.get_available_tools()
    tools_description = await tool_manager.get_tools_system_prompt()

    tools_used: List[str] = []
    tool_iteration = 0
    max_tool_iterations = 3

    # Context temporale / geografico
    try:
        from zoneinfo import ZoneInfo
    except ImportError:  # pragma: no cover - fallback per versioni vecchie
        try:
            from backports.zoneinfo import ZoneInfo  # type: ignore
        except ImportError:
            ZoneInfo = None  # type: ignore

    try:
        tz_str = os.environ.get("TZ", "Europe/Rome")
        if ZoneInfo:
            try:
                tz = ZoneInfo(tz_str)
            except Exception:  # pragma: no cover - fallback
                tz = ZoneInfo("Europe/Rome")  # type: ignore
        else:
            tz = None

        current_time = datetime.now(tz) if tz else datetime.now()
        current_time_str = current_time.strftime("%H:%M:%S")

        day_names = {
            "Monday": "lunedì",
            "Tuesday": "martedì",
            "Wednesday": "mercoledì",
            "Thursday": "giovedì",
            "Friday": "venerdì",
            "Saturday": "sabato",
            "Sunday": "domenica",
        }
        day_name = day_names.get(current_time.strftime("%A"), current_time.strftime("%A"))

        month_names = {
            "January": "gennaio",
            "February": "febbraio",
            "March": "marzo",
            "April": "aprile",
            "May": "maggio",
            "June": "giugno",
            "July": "luglio",
            "August": "agosto",
            "September": "settembre",
            "October": "ottobre",
            "November": "novembre",
            "December": "dicembre",
        }
        month_name = month_names.get(current_time.strftime("%B"), current_time.strftime("%B"))

        date_italian = f"{day_name}, {current_time.day} {month_name} {current_time.year}"
        timezone_name = (tz_str or "local").replace("_", " ")
        location = os.environ.get("USER_LOCATION", "Italia")

        time_context = f"""
=== CONTESTO TEMPORALE E GEOGRAFICO ===
Data e ora corrente: {date_italian}, {current_time_str} ({timezone_name})
Località: {location}
Giorno della settimana: {day_name}

        === REGOLE DI CONVERSAZIONE ===
- Se l'utente fa una DOMANDA, rispondi in modo completo e utile
- Se l'utente fa una RICHIESTA DI AZIONE (es: "leggi", "controlla", "cerca", "recupera", "vedi", "mostra"), DEVI chiamare i tool appropriati per eseguire l'azione richiesta. NON rispondere solo con "Ok" o "Capito" senza eseguire l'azione.
- Se l'utente fa un'AFFERMAZIONE puramente informativa (fornisce informazioni senza richiedere azioni), rispondi brevemente:
  * "Ok", "Perfetto", "Capito", "D'accordo" sono risposte appropriate
  * Non è necessario cercare sempre una risposta elaborata
  * Riconosci semplicemente l'informazione ricevuta
- IMPORTANTE: Distingui tra richieste di azione e affermazioni informative. Se l'utente chiede di fare qualcosa (leggere, controllare, cercare, ecc.), DEVI usare i tool disponibili.
- Sii naturale e conversazionale - non essere verboso quando non necessario

⚠️ IMPORTANTE - WhatsApp Integration:
L'integrazione WhatsApp basata su Selenium è stata rimossa. Non esistono tool get_whatsapp_messages o send_whatsapp_message al momento. Se l'utente chiede qualcosa su WhatsApp, informa che l'integrazione WhatsApp non è disponibile e che verrà reintrodotta in futuro tramite le Business API. NON inventare risposte sui messaggi WhatsApp.

# WhatsApp integration temporarily disabled - will be re-enabled with Business API
# 🔴 REGOLE CRITICHE per richieste WhatsApp (QUANDO RIABILITATA):
# 1. Se l'utente chiede QUALSIASI cosa su WhatsApp (messaggi, cosa ho ricevuto, messaggi di oggi, etc.), DEVI SEMPRE chiamare il tool get_whatsapp_messages PRIMA di rispondere
# 2. NON assumere mai che WhatsApp non sia configurato senza aver chiamato il tool
# 3. NON dire mai "non ho accesso" o "non posso" senza aver chiamato il tool
# 4. Se l'utente chiede "messaggi di oggi", "cosa ho ricevuto oggi", "che messaggi ho ricevuto oggi", DEVI usare date_filter='today'
# 5. Se l'utente chiede "ieri", usa date_filter='yesterday'
# 6. Se il tool restituisce count=0, significa che non ci sono messaggi per quella data, NON che WhatsApp non è configurato
# 7. Se il tool restituisce un errore esplicito, allora puoi dire che WhatsApp potrebbe non essere configurato
"""
    except Exception as exc:  # pragma: no cover - fallback
        logger.warning("Errore nel calcolare il contesto temporale: %s", exc)
        time_context = ""

    current_prompt = request.message
    response_text = ""
    tool_results: List[Dict[str, Any]] = []
    response_data: Any = None
    tool_calls: List[Dict[str, Any]] = []

    while tool_iteration < max_tool_iterations:
        logger.info("Tool calling iteration %s, prompt length: %s", tool_iteration, len(current_prompt))
        iteration_tool_results: List[Dict[str, Any]] = []

        # Force web_search se richiesto la prima volta
        if request.force_web_search and tool_iteration == 0:
            logger.info("🔍 Force web_search abilitato - query: %s", request.message)
            try:
                web_search_result = await tool_manager.execute_tool(
                    "web_search",
                    {"query": request.message},
                    db=db,
                    session_id=session_id,
                )
                iteration_tool_results.append(
                    {
                        "tool": "web_search",
                        "parameters": {"query": request.message},
                        "result": web_search_result,
                    }
                )
                tools_used.append("web_search")
                tool_iteration += 1
            except Exception as exc:
                logger.error("Errore durante force_web_search: %s", exc, exc_info=True)

        if not iteration_tool_results:
            try:
                pass_tools = available_tools if tool_iteration == 0 else None
                pass_tools_description = tools_description if tool_iteration == 0 and not available_tools else None
                ollama._time_context = time_context

                response_data = await ollama.generate_with_context(
                    prompt=current_prompt,
                    session_context=session_context,
                    retrieved_memory=retrieved_memory if retrieved_memory else None,
                    tools=pass_tools,
                    tools_description=pass_tools_description,
                    return_raw=True,
                )

                if isinstance(response_data, dict):
                    response_text = response_data.get("content", "")
                    parsed_tc = response_data.get("_parsed_tool_calls")
                    if parsed_tc:
                        tool_calls = parsed_tc
                    else:
                        message = response_data.get("raw_result", {}).get("message")
                        if isinstance(message, dict) and "tool_calls" in message:
                            tool_calls = [
                                {
                                    "name": tc.get("function", {}).get("name"),
                                    "parameters": tc.get("function", {}).get("arguments", {}),
                                }
                                for tc in message["tool_calls"]
                                if isinstance(tc, dict)
                            ]
                else:
                    response_text = response_data or ""

                logger.info("Ollama response length=%s", len(response_text or ""))
            except Exception as exc:
                logger.error("Errore chiamando Ollama: %s", exc, exc_info=True)
                response_text = f"Errore nella chiamata al modello: {exc}"
                break

            if not response_text.strip() and not tool_calls:
                response_text = "Mi scuso, ho riscontrato un problema nella generazione della risposta. Per favore riprova."
                break

        if tool_calls:
            for tool_call in tool_calls:
                tool_name = tool_call.get("name")
                tool_params = tool_call.get("parameters", {})
                if tool_name:
                    try:
                        result = await tool_manager.execute_tool(tool_name, tool_params, db, session_id=session_id)
                        iteration_tool_results.append(
                            {
                                "tool": tool_name,
                                "parameters": tool_params,
                                "result": result,
                            }
                        )
                        tools_used.append(tool_name)
                    except Exception as exc:
                        logger.error("Errore eseguendo tool %s: %s", tool_name, exc, exc_info=True)
                        iteration_tool_results.append(
                            {
                                "tool": tool_name,
                                "parameters": tool_params,
                                "result": {"error": str(exc)},
                            }
                        )

        if iteration_tool_results:
            tool_results_text = "\n\n=== Risultati Tool Chiamati ===\n"
            for tr in iteration_tool_results:
                tool_name = tr["tool"]
                wrapper_result = tr["result"]
                tool_results_text += f"Tool: {tool_name}\n"
                if isinstance(wrapper_result, dict):
                    result_str = json_lib.dumps(wrapper_result, indent=2, ensure_ascii=False, default=str)
                else:
                    result_str = str(wrapper_result)
                tool_results_text += f"{result_str}\n\n"

            current_prompt = f"""{request.message}

{tool_results_text}

Alla luce dei risultati dei tool sopra, genera ora la risposta finale per l'utente."""
            tool_results.extend(iteration_tool_results)
            tool_calls = []
            tool_iteration += 1
            continue

        break

    # Messaggio assistente e salvataggio
    # Get tenant_id from session if not provided
    if not tenant_id:
        from sqlalchemy import select
        result = await db.execute(
            select(SessionModel.tenant_id).where(SessionModel.id == session_id)
        )
        tenant_id = result.scalar_one_or_none()
    
    assistant_message = MessageModel(
        session_id=session_id,
        tenant_id=tenant_id,
        role="assistant",
        content=response_text,
        session_metadata={"memory_used": memory_used, "tools_used": tools_used},
    )
    db.add(assistant_message)
    await db.commit()

    # Notifiche (contraddizioni, ecc.)
    notification_service = NotificationService(db)
    pending_notifications = await notification_service.get_pending_notifications(
        session_id=session_id,
        read=False,
        tenant_id=tenant_id,
    )
    notification_count = len(pending_notifications)

    high_urgency = [
        n
        for n in pending_notifications
        if n.get("urgency") == "high" and n.get("content", {}).get("status_update")
    ]
    formatted_high_notifications: List[Dict[str, Any]] = []

    for notif in high_urgency:
        formatted_high_notifications.append(
            {
                "type": notif.get("type"),
                "urgency": notif.get("urgency"),
                "content": notif.get("content"),
                "id": notif.get("id"),
            }
        )

    # Segna notifiche come lette dopo averle raccolte
    if pending_notifications:
        await notification_service.mark_as_read(
            [notif["id"] for notif in pending_notifications if notif.get("id")]
        )

    tool_details = [
        ToolExecutionDetail(
            tool_name=tr["tool"],
            parameters=tr.get("parameters", {}),
            result=tr.get("result", {}),
            success=not isinstance(tr.get("result"), dict) or "error" not in tr["result"],
        )
        for tr in tool_results
    ]

    return ChatResponse(
        response=response_text,
        session_id=session_id,
        memory_used=memory_used,
        tools_used=tools_used,
        tool_details=tool_details,
        notifications_count=notification_count,
        high_urgency_notifications=formatted_high_notifications,
    )