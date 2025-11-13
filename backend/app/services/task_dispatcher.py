from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Callable, Dict, Optional, Set
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Message as MessageModel, Session as SessionModel
from app.models.schemas import ChatRequest
from app.services.agent_activity_stream import AgentActivityStream
from app.services.background_task_manager import BackgroundTaskManager
from app.services.task_queue import TaskQueue, TaskStatus
from app.services.task_queue import Task
from app.core.config import settings
from app.core.memory_manager import MemoryManager
from app.core.ollama_client import OllamaClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TaskPromptConfig:
    """
    Configuration describing how to trigger LangGraph for a given task type.
    """

    message: str
    use_memory: bool = False
    system_log: Optional[str] = None


DEFAULT_TASK_PROMPT = TaskPromptConfig(message="[auto-task]")

TASK_PROMPTS: Dict[str, TaskPromptConfig] = {
    "resolve_contradiction": TaskPromptConfig(
        message="[auto-task] resolve_contradiction",
        use_memory=False,
        system_log="Attivazione automatica per la risoluzione di una contraddizione.",
    ),
}


class TaskDispatcher:
    """
    Converts queued tasks into LangGraph turns so that the Main agent can
    parlare con l'utente senza attendere un messaggio manuale.
    """

    def __init__(
        self,
        *,
        task_queue: TaskQueue,
        background_tasks: BackgroundTaskManager,
        session_factory: Callable[[], AsyncSession],
        agent_activity_stream: AgentActivityStream,
        memory_manager: MemoryManager,
        ollama_client: OllamaClient,
        planner_client: OllamaClient,
    ) -> None:
        self._task_queue = task_queue
        self._background_tasks = background_tasks
        self._session_factory = session_factory
        self._agent_activity_stream = agent_activity_stream
        self._memory_manager = memory_manager
        self._ollama_client = ollama_client
        self._planner_client = planner_client

        self._locks: Dict[UUID, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._pending: Set[UUID] = set()

    def schedule_dispatch(self, session_id: UUID) -> None:
        """
        Schedule a dispatch run for the provided session.
        Multiple requests collapse into a single background coroutine.
        """

        if session_id in self._pending:
            return

        self._pending.add(session_id)

        async def _runner() -> None:
            try:
                await self._dispatch_session(session_id)
            finally:
                self._pending.discard(session_id)

        self._background_tasks.schedule_coroutine(
            _runner(), name=f"task-dispatch-{session_id}"
        )

    async def _dispatch_session(self, session_id: UUID) -> None:
        lock = self._locks[session_id]
        async with lock:
            logger.info(
                "🚀 Dispatcher: checking session %s for queued tasks", session_id
            )
            
            # First, check for queued tasks (highest priority)
            queued = self._task_queue.find_task_by_status(
                session_id, TaskStatus.QUEUED
            )
            if queued:
                logger.info(
                    "✅ Dispatcher: found queued task %s (%s) for session %s, processing...",
                    queued.id,
                    queued.type,
                    session_id,
                )
            else:
                # Check if there's already a task IN_PROGRESS - don't process duplicates
                in_progress = self._task_queue.find_task_by_status(
                    session_id, TaskStatus.IN_PROGRESS
                )
                if in_progress:
                    logger.info(
                        "⏸️  Dispatcher: task %s (%s) already IN_PROGRESS for session %s, skipping duplicate processing.",
                        in_progress.id,
                        in_progress.type,
                        session_id,
                    )
                    return
                # If no queued tasks, check for waiting tasks that might need to be re-presented
                waiting = self._task_queue.find_task_by_status(
                    session_id, TaskStatus.WAITING_USER
                )
                if waiting:
                    # Check if the waiting task is old (more than 5 minutes) - might need to be re-presented
                    age = datetime.now(UTC) - waiting.created_at
                    if age > timedelta(minutes=5):
                        logger.info(
                            "🔄 Dispatcher: found old waiting task %s (%s, age=%s) for session %s, re-processing...",
                            waiting.id,
                            waiting.type,
                            age,
                            session_id,
                        )
                        queued = waiting  # Treat as queued to re-process
                    else:
                        logger.info(
                            "⏸️  Session %s already has a task waiting for user input (%s, age=%s), skipping dispatch.",
                            session_id,
                            waiting.type,
                            age,
                        )
                        return
                else:
                    logger.debug(
                        "No queued or waiting tasks for session %s, skipping dispatch.", session_id
                    )
                    return
            
            if not queued:
                return

            # Mark task as IN_PROGRESS before processing to prevent duplicate processing
            try:
                self._task_queue.update_task(
                    session_id,
                    queued.id,
                    status=TaskStatus.IN_PROGRESS,
                )
                logger.info(
                    "📌 Dispatcher: marked task %s as IN_PROGRESS before processing",
                    queued.id,
                )
            except Exception as exc:
                logger.warning(
                    "⚠️  Dispatcher: failed to mark task %s as IN_PROGRESS: %s",
                    queued.id,
                    exc,
                )
                # Continue anyway - the task might have been processed by another instance

            config = TASK_PROMPTS.get(queued.type, DEFAULT_TASK_PROMPT)

            try:
                async with self._session_factory() as db:
                    await self._execute_dispatch(
                        db=db,
                        session_id=session_id,
                        queued_task=queued,
                        config=config,
                    )
            except Exception as exc:  # pragma: no cover - safeguard
                logger.error(
                    "Task dispatch failed for session %s: %s", session_id, exc, exc_info=True
                )

    async def _execute_dispatch(
        self,
        *,
        db: AsyncSession,
        session_id: UUID,
        queued_task: Task,
        config: TaskPromptConfig,
    ) -> None:
        # Fetch session and messages
        result = await db.execute(
            select(SessionModel).where(SessionModel.id == session_id)
        )
        session = result.scalar_one_or_none()
        if not session:
            logger.warning(
                "Session %s not found while dispatching tasks; dropping queued items.",
                session_id,
            )
            return

        messages_result = await db.execute(
            select(MessageModel)
            .where(MessageModel.session_id == session_id)
            .order_by(MessageModel.timestamp)
        )
        previous_messages = messages_result.scalars().all()
        all_messages_dict = [
            {"role": str(msg.role), "content": str(msg.content)}
            for msg in previous_messages
        ]

        # Only create system log message if this is the first time processing this task
        # Check if a system message with this content already exists for this session
        if config.system_log:
            existing_system_msg = await db.execute(
                select(MessageModel)
                .where(MessageModel.session_id == session_id)
                .where(MessageModel.role == "system")
                .where(MessageModel.content == config.system_log)
                .order_by(MessageModel.timestamp.desc())
                .limit(1)
            )
            if not existing_system_msg.scalar_one_or_none():
                # Only create if it doesn't exist
                system_message = MessageModel(
                    session_id=session_id,
                    role="system",
                    content=config.system_log,
                )
                db.add(system_message)
                logger.debug(
                    "📝 Dispatcher: created system log message for task %s",
                    queued_task.id,
                )
            else:
                logger.debug(
                    "⏭️  Dispatcher: system log message already exists for task %s, skipping duplicate",
                    queued_task.id,
                )

        pending_plan = dict(session.session_metadata or {}).get("pending_plan")

        request = ChatRequest(
            message=config.message,
            session_id=session_id,
            use_memory=config.use_memory,
        )

        self._publish_activity(
            session_id,
            status="started",
            message=f"Dispatch automatico per task {queued_task.type}",
        )

        # Minimal context: we keep latest messages, memory off by default.
        recent_window = settings.context_keep_recent_messages or 10
        session_context = all_messages_dict[-recent_window:]
        retrieved_memory: list[str] = []
        memory_used = {
            "short_term": False,
            "medium_term": [],
            "long_term": [],
            "files": [],
        }

        from app.agents import run_langgraph_chat  # Local import to avoid circular dependency

        langgraph_result = await run_langgraph_chat(
            db=db,
            session_id=session_id,
            request=request,
            ollama=self._ollama_client,
            planner_client=self._planner_client,
            agent_activity_stream=self._agent_activity_stream,
            memory_manager=self._memory_manager,
            session_context=session_context,
            retrieved_memory=retrieved_memory,
            memory_used=memory_used,
            previous_messages=all_messages_dict,
            pending_plan=pending_plan,
        )

        chat_response = langgraph_result["chat_response"]
        new_plan_metadata = langgraph_result.get("plan_metadata")
        assistant_message_saved = langgraph_result.get("assistant_message_saved", False)

        # Persist assistant message if LangGraph did not already do it
        if not assistant_message_saved:
            assistant_message = MessageModel(
                session_id=session_id,
                role="assistant",
                content=chat_response.response,
                session_metadata={
                    "memory_used": chat_response.memory_used,
                    "tools_used": chat_response.tools_used,
                },
            )
            db.add(assistant_message)

        session_metadata = dict(session.session_metadata or {})

        if new_plan_metadata:
            session_metadata["pending_plan"] = new_plan_metadata
        else:
            session_metadata.pop("pending_plan", None)

        session.session_metadata = session_metadata
        await db.commit()

        # Broadcast agent activity events to ensure frontend telemetry updates
        for event in chat_response.agent_activity:
            self._agent_activity_stream.publish(session_id, event)

        logger.info(
            "✅ Dispatcher: successfully processed task %s (%s) for session %s. Response: %.100s",
            queued_task.id,
            queued_task.type,
            session_id,
            chat_response.response[:100] if chat_response.response else "(empty)",
        )
        
        self._publish_activity(
            session_id,
            status="completed",
            message=f"Task {queued_task.type} dispatch completato",
        )

    def _publish_activity(self, session_id: UUID, *, status: str, message: str) -> None:
        event = {
            "agent_id": "task_scheduler",
            "agent_name": "Task Scheduler",
            "status": status,
            "message": message,
            "timestamp": datetime.now(UTC),
        }
        self._agent_activity_stream.publish(session_id, event)


