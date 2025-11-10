import asyncio
import logging
from contextlib import suppress
from datetime import UTC, datetime
from typing import Optional
from uuid import UUID

from app.db.database import AsyncSessionLocal
from app.services.background_agent import BackgroundAgent
from app.core.memory_manager import MemoryManager
from app.services.agent_activity_stream import AgentActivityStream

logger = logging.getLogger(__name__)


class BackgroundTaskManager:
    """
    Lightweight in-process scheduler for background agent activities.

    Tasks are fire-and-forget, errors are logged and never propagated to the caller.
    """

    def __init__(self) -> None:
        self._tasks: set[asyncio.Task] = set()
        self._loop = asyncio.get_event_loop()

    def _track_task(self, task: asyncio.Task) -> None:
        self._tasks.add(task)

        def _done_callback(t: asyncio.Task) -> None:
            with suppress(KeyError):
                self._tasks.discard(t)
            if t.exception():
                logger.error("Background task finished with error", exc_info=t.exception())

        task.add_done_callback(_done_callback)

    def schedule_contradiction_check(
        self,
        *,
        session_id: UUID,
        message: str,
        memory_manager: MemoryManager,
        agent_activity_stream: Optional[AgentActivityStream] = None,
    ) -> None:
        """
        Launch contradiction analysis in the background without blocking the main flow.
        """

        async def _runner() -> None:
            activity_agent_id = "background_integrity_agent"

            def _publish(status: str, extra: Optional[dict] = None) -> None:
                if not agent_activity_stream:
                    return
                event = {
                    "agent_id": activity_agent_id,
                    "agent_name": "Background Integrity Agent",
                    "status": status,
                    "timestamp": datetime.now(UTC),
                }
                if extra:
                    event.update(extra)
                agent_activity_stream.publish(session_id, event)

            _publish("started", {"message": "Analisi contraddizioni avviata"})

            try:
                async with AsyncSessionLocal() as db_session:
                    agent = BackgroundAgent(
                        memory_manager=memory_manager,
                        db=db_session,
                    )
                    knowledge = {
                        "type": "user_statement",
                        "content": message,
                        "importance": 0.5,
                    }
                    logger.info(
                        "🔍 [BG] Checking contradictions for message (session=%s): %.50s",
                        session_id,
                        message,
                    )
                    await agent.process_new_knowledge(
                        knowledge_item=knowledge,
                        session_id=session_id,
                    )
                    logger.info(
                        "✅ [BG] Contradiction analysis complete for session %s",
                        session_id,
                    )
                    _publish("completed")
            except Exception as exc:
                logger.warning(
                    "Background contradiction check failed for session %s: %s",
                    session_id,
                    exc,
                    exc_info=True,
                )
                _publish("error", {"message": str(exc)})

        task = self._loop.create_task(_runner(), name=f"contradiction-{session_id}")
        self._track_task(task)

    def active_tasks(self) -> int:
        return len(self._tasks)


