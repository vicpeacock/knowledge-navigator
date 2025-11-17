from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Awaitable, Callable, Dict, List, Optional, Set, Tuple, TYPE_CHECKING
from uuid import UUID

from app.services.task_queue import TaskQueue, Task, TaskStatus

if TYPE_CHECKING:
    from app.services.task_dispatcher import TaskDispatcher
    from app.services.agent_activity_stream import AgentActivityStream

logger = logging.getLogger(__name__)

ScheduledTask = Tuple[UUID, Task]
PollerCallable = Callable[[], Awaitable[List[ScheduledTask]]]


@dataclass
class ScheduledAgent:
    name: str
    interval_seconds: int
    poller: PollerCallable
    last_run: datetime = field(
        default_factory=lambda: datetime.fromtimestamp(0, tz=UTC)
    )


class AgentScheduler:
    """
    Periodically polls registered agents to produce tasks for the queue.
    """

    def __init__(
        self,
        task_queue: TaskQueue,
        tick_seconds: int = 30,
        dispatcher: Optional["TaskDispatcher"] = None,
        agent_activity_stream: Optional["AgentActivityStream"] = None,
    ) -> None:
        self._task_queue = task_queue
        self._tick = max(5, tick_seconds)
        self._agents: Dict[str, ScheduledAgent] = {}
        self._running = False
        self._dispatcher: Optional["TaskDispatcher"] = dispatcher
        self._agent_activity_stream = agent_activity_stream

    def register_agent(self, agent: ScheduledAgent) -> None:
        logger.info(
            "Registered scheduled agent %s (interval=%ss)",
            agent.name,
            agent.interval_seconds,
        )
        self._agents[agent.name] = agent

    def register_dispatcher(self, dispatcher: "TaskDispatcher") -> None:
        self._dispatcher = dispatcher

    async def run_forever(self) -> None:
        if self._running:
            return

        self._running = True
        try:
            while True:
                await self._poll_agents()
                await asyncio.sleep(self._tick)
        finally:
            self._running = False

    async def _poll_agents(self) -> None:
        if not self._agents:
            return

        now = datetime.now(UTC)
        sessions_to_dispatch: Set[UUID] = set()

        for agent in self._agents.values():
            due = agent.last_run + timedelta(seconds=agent.interval_seconds)
            if now < due:
                continue

            logger.debug("Polling scheduled agent %s", agent.name)
            
            # DON'T publish activity event for polling - only publish when tasks are actually found
            # This prevents the integrity agent from appearing active when there are no contradictions
            
            try:
                tasks = await agent.poller()
                
                # Only publish activity event if tasks are actually found
                # This ensures the integrity agent only appears active when there are real contradictions to process
                if self._agent_activity_stream and tasks:
                    logger.info(f"📋 Found {len(tasks)} tasks from {agent.name}, publishing activity events")
                    self._publish_activity(
                        agent_id="background_integrity_agent",
                        agent_name="Background Integrity Agent",
                        status="started",
                        message=f"Found {len(tasks)} pending contradiction(s)",
                    )
                elif tasks:
                    logger.debug(f"Found {len(tasks)} tasks from {agent.name}, but no activity stream available")
                else:
                    logger.debug(f"No tasks found from {agent.name}, skipping activity events")
            except Exception as exc:  # pragma: no cover - safeguard
                logger.warning(
                    "Scheduled agent %s failed during poll: %s",
                    agent.name,
                    exc,
                    exc_info=True,
                )
                if self._agent_activity_stream:
                    self._publish_activity(
                        agent_id="task_scheduler",
                        agent_name="Task Scheduler",
                        status="error",
                        message=f"Error polling {agent.name}: {exc}",
                    )
                agent.last_run = now
                continue

            for session_id, task in tasks:
                self._task_queue.enqueue(session_id, task)
                logger.info(
                    "Agent %s enqueued task %s for session %s (task_id=%s)",
                    agent.name,
                    task.type,
                    session_id,
                    task.id,
                )
                sessions_to_dispatch.add(session_id)
                
                # Publish activity event for specific session
                if self._agent_activity_stream:
                    self._publish_activity_for_session(
                        session_id,
                        agent_id="background_integrity_agent",
                        agent_name="Background Integrity Agent",
                        status="started",
                        message=f"Enqueued {task.type} task",
                    )

            # Publish completion event ONLY if tasks were found
            # This prevents the integrity agent from appearing active when there are no contradictions
            if self._agent_activity_stream and tasks:
                self._publish_activity(
                    agent_id="background_integrity_agent",
                    agent_name="Background Integrity Agent",
                    status="completed",
                    message=f"Processed {len(tasks)} contradiction(s)",
                )
                # NOTE: task_scheduler events are now suppressed in _publish_activity
                # to prevent the scheduler from appearing active when idle
            # If no tasks found, don't publish any events - the agent should appear idle

            agent.last_run = now

        # Also check for old waiting_user tasks that need to be re-processed
        if self._dispatcher:
            for session_id, tasks in self._task_queue._tasks.items():
                for task in tasks.values():
                    if task.status == TaskStatus.WAITING_USER:
                        age = now - task.created_at
                        if age > timedelta(minutes=5):
                            logger.info(
                                "🔄 Scheduler: found old waiting task %s (age=%s) for session %s, triggering dispatcher",
                                task.id,
                                age,
                                session_id,
                            )
                            sessions_to_dispatch.add(session_id)
                            break  # Only trigger once per session

        if self._dispatcher and sessions_to_dispatch:
            for session_id in sessions_to_dispatch:
                try:
                    self._dispatcher.schedule_dispatch(session_id)
                except Exception as exc:  # pragma: no cover - safeguard
                    logger.warning(
                        "Failed to schedule dispatch for session %s: %s",
                        session_id,
                        exc,
                        exc_info=True,
                    )
    
    def _publish_activity(
        self,
        *,
        agent_id: str,
        agent_name: str,
        status: str,
        message: Optional[str] = None,
    ) -> None:
        """Publish activity event to all active sessions (with subscribers)."""
        if not self._agent_activity_stream:
            logger.warning("Agent activity stream not available, skipping publish")
            return
        
        # IMPORTANT: Don't publish task_scheduler events unless there are actual tasks
        # This prevents the integrity agent from appearing active when idle
        if agent_id == "task_scheduler" and status in ["started", "completed"]:
            # Only log at debug level - don't publish to frontend
            logger.debug(
                "Skipping task_scheduler event (%s) - only publish when tasks are found",
                status
            )
            return
        
        event = {
            "agent_id": agent_id,
            "agent_name": agent_name,
            "status": status,
            "message": message,
            "timestamp": datetime.now(UTC),
        }
        
        # Get active sessions before publishing
        active_sessions = self._agent_activity_stream.get_active_sessions()
        logger.info(
            "📡 Publishing activity event for %s (%s) to %d active session(s)",
            agent_id,
            status,
            len(active_sessions),
        )
        
        if not active_sessions:
            logger.warning("⚠️  No active sessions, event will not be delivered")
        
        # Publish to all sessions with active subscribers (frontend connections)
        self._agent_activity_stream.publish_to_all_active_sessions(event)
    
    def _publish_activity_for_session(
        self,
        session_id: UUID,
        *,
        agent_id: str,
        agent_name: str,
        status: str,
        message: Optional[str] = None,
    ) -> None:
        """Publish activity event to a specific session."""
        if not self._agent_activity_stream:
            return
        
        event = {
            "agent_id": agent_id,
            "agent_name": agent_name,
            "status": status,
            "message": message,
            "timestamp": datetime.now(UTC),
        }
        
        self._agent_activity_stream.publish(session_id, event)


