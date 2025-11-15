"""
Background Agent - Autonomous thinking agent for proactive checks
"""
import logging
from typing import Dict, Any, Optional, List, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.memory_manager import MemoryManager
from app.core.ollama_client import OllamaClient
from app.db.database import AsyncSessionLocal
from app.services.notification_service import NotificationService
from app.services.semantic_integrity_checker import SemanticIntegrityChecker
from app.services.task_queue import TaskQueue, Task, TaskPriority, TaskStatus

logger = logging.getLogger(__name__)


class BackgroundAgent:
    """
    Background agent for autonomous thinking.
    Handles: semantic integrity, external events, todo list, etc.
    """

    def __init__(
        self,
        memory_manager: MemoryManager,
        db: AsyncSession,
        ollama_client: Optional[OllamaClient] = None,
        task_queue: Optional[TaskQueue] = None,
    ):
        self.memory_manager = memory_manager
        self.db = db
        self.task_queue = task_queue

        # Use background Ollama client (phi3:mini) for background tasks
        self.ollama_client = ollama_client or self._create_background_client()

        # Initialize services
        self.integrity_checker = SemanticIntegrityChecker(
            memory_manager=memory_manager,
            ollama_client=self.ollama_client,  # Use background client
        )
        self.notification_service = NotificationService(db=db)

    async def process_new_knowledge(
        self,
        knowledge_item: Dict[str, Any],
        session_id: Optional[UUID] = None,
    ):
        """
        Process new knowledge in background:
        - Check semantic integrity
        - Generate notifications if necessary

        Args:
            knowledge_item: Knowledge item from ConversationLearner
            session_id: Session ID where knowledge was extracted
        """
        if not self.integrity_checker.enabled:
            logger.info(
                "Skipping contradiction analysis for '%s': background integrity checker disabled",
                knowledge_item.get("content", "")[:50],
            )
            return

        try:
            logger.info(f"Processing new knowledge in background: {knowledge_item.get('content', '')[:50]}...")

            # Check integrity (exhaustive or limited based on config)
            contradiction_info = await self.integrity_checker.check_contradictions(
                knowledge_item,
                db=self.db,
                max_similar_memories=settings.integrity_max_similar_memories,
                confidence_threshold=settings.integrity_confidence_threshold,
            )

            logger.info(f"Integrity check result: has_contradiction={contradiction_info.get('has_contradiction')}, confidence={contradiction_info.get('confidence', 0):.2f}, contradictions_count={len(contradiction_info.get('contradictions', []))}")

            if contradiction_info.get("has_contradiction"):
                logger.warning(f"⚠️ Contradiction detected for knowledge: {knowledge_item.get('content', '')[:50]}...")
                logger.warning(f"   Confidence: {contradiction_info.get('confidence', 0):.2f}, Count: {len(contradiction_info.get('contradictions', []))}")

                # STEP 1: Write to status update (create notification in database)
                # This is the "status update" - stored in database for Main to process
                # Get tenant_id from session if available
                tenant_id = None
                if session_id:
                    from app.models.database import Session as SessionModel
                    from sqlalchemy import select
                    result = await self.db.execute(
                        select(SessionModel.tenant_id).where(SessionModel.id == session_id)
                    )
                    tenant_id = result.scalar_one_or_none()
                
                notification = await self.notification_service.create_notification(
                    type="contradiction",
                    urgency="high",  # Initial urgency - Main will decide final urgency
                    content={
                        "new_knowledge": knowledge_item,
                        "contradictions": contradiction_info.get("contradictions", []),
                        "confidence": contradiction_info.get("confidence", 0.0),
                        "status_update": True,  # Flag to indicate this should appear in status update
                    },
                    session_id=session_id,
                    tenant_id=tenant_id,
                )

                logger.info(f"✅ Created contradiction notification {notification.id} for session {session_id} (status update written)")

                # STEP 2: Notify Main asynchronously (Main will decide notification type)
                # The Main process will check for new notifications when generating response
                # and decide the final urgency level and format
                logger.info(f"📢 Contradiction notification sent to Main for processing (session {session_id})")

                if self.task_queue and session_id:
                    task_payload = {
                        "new_statement": knowledge_item.get("content"),
                        "contradictions": contradiction_info.get("contradictions", []),
                        "confidence": contradiction_info.get("confidence", 0.0),
                        "notification_id": notification.id if notification else None,
                    }
                    task = Task(
                        type="resolve_contradiction",
                        origin="background_integrity_agent",
                        priority=TaskPriority.HIGH,
                        payload=task_payload,
                    )
                    self.task_queue.enqueue(session_id, task)
                    logger.info(
                        "📝 Enqueued contradiction resolution task %s for session %s",
                        task.id,
                        session_id,
                    )
            else:
                logger.info(f"No contradictions found for knowledge: {knowledge_item.get('content', '')[:50]}... (confidence: {contradiction_info.get('confidence', 0):.2f})")

        except Exception as e:
            logger.error(f"Error processing new knowledge in background: {e}", exc_info=True)
            # Don't raise - background tasks should not fail the main flow

    @staticmethod
    def _create_background_client() -> Optional[OllamaClient]:
        try:
            if settings.use_llama_cpp_background:
                from app.core.llama_cpp_client import LlamaCppClient

                return LlamaCppClient(
                    base_url=settings.ollama_background_base_url,
                    model=settings.ollama_background_model,
                )

            return OllamaClient(
                base_url=settings.ollama_background_base_url,
                model=settings.ollama_background_model,
            )
        except Exception as exc:
            logger.warning(
                "Background Ollama client unavailable (%s). Background tasks will be disabled.",
                exc,
            )
            return None
    
    async def check_external_events(self):
        """Check external events (email, calendar, etc.) - to be implemented"""
        # TODO: Implement event checking
        pass
    
    async def check_todo_list(self):
        """Check todo list - to be implemented"""
        # TODO: Implement todo list checking
        pass


async def fetch_pending_contradiction_tasks(
    task_queue: TaskQueue,
) -> List[Tuple[UUID, Task]]:
    """
    Inspect stored notifications and generate queue tasks for unresolved contradictions.
    """
    results: List[Tuple[UUID, Task]] = []
    
    # Clear completed tasks for all sessions to avoid stale tasks blocking new ones
    # This ensures we only check for active tasks (QUEUED, IN_PROGRESS, WAITING_USER)
    total_before = sum(len(tasks) for tasks in task_queue._tasks.values())
    for session_id in list(task_queue._tasks.keys()):
        task_queue.clear_completed(session_id)
    total_after = sum(len(tasks) for tasks in task_queue._tasks.values())
    if total_before > 0:
        logger.debug(
            "🧹 Cleared completed tasks: %d total before, %d total after",
            total_before,
            total_after,
        )

    async with AsyncSessionLocal() as db_session:
        service = NotificationService(db_session)
        pending = await service.get_pending_notifications(read=False)
        
        logger.info(
            "🔍 Scheduler poller: found %d pending notifications (all types)",
            len(pending),
        )

        contradiction_count = 0
        skipped_count = 0
        
        for notification in pending:
            if notification.get("type") != "contradiction":
                continue
            
            contradiction_count += 1
            session_id = notification.get("session_id")
            if not session_id:
                logger.debug("Skipping contradiction notification without session_id")
                continue

            try:
                session_uuid = UUID(session_id)
            except ValueError:
                logger.warning("Invalid session_id in notification: %s", session_id)
                continue

            # Check if there's already an active task for this contradiction
            # First, log the state of the queue for this session
            session_tasks = task_queue._tasks.get(session_uuid, {})
            active_tasks = [
                t for t in session_tasks.values()
                if t.status in [TaskStatus.QUEUED, TaskStatus.IN_PROGRESS, TaskStatus.WAITING_USER]
            ]
            logger.info(
                "🔍 Checking session %s: %d total tasks, %d active tasks",
                session_uuid,
                len(session_tasks),
                len(active_tasks),
            )
            
            existing_task = task_queue.find_task_by_type(
                session_uuid,
                "resolve_contradiction",
                statuses=[
                    TaskStatus.QUEUED,
                    TaskStatus.IN_PROGRESS,
                    TaskStatus.WAITING_USER,
                ],
            )
            if existing_task:
                skipped_count += 1
                logger.info(
                    "⏭️  Skipping contradiction for session %s: task already exists (id=%s, status=%s, created=%s)",
                    session_uuid,
                    existing_task.id,
                    existing_task.status.value,
                    existing_task.created_at,
                )
                continue
            
            # TEMPORARY: Force creation of tasks to debug why they're not being created
            # Remove this after debugging
            logger.info(
                "✅ No existing task found for session %s, creating new task",
                session_uuid,
            )
            
            # Log when we're about to create a new task
            logger.debug(
                "✅ No existing task found for session %s, will create new task",
                session_uuid,
            )

            content = notification.get("content") or {}
            new_knowledge = content.get("new_knowledge") or {}
            new_statement = new_knowledge.get("content") or new_knowledge.get("text") or ""
            contradictions = content.get("contradictions", [])
            confidence = content.get("confidence", 0.0)

            task = Task(
                type="resolve_contradiction",
                origin="background_integrity_agent",
                priority=TaskPriority.HIGH,
                payload={
                    "new_statement": new_statement,
                    "contradictions": contradictions,
                    "confidence": confidence,
                    "notification_id": notification.get("id"),
                },
            )
            results.append((session_uuid, task))
            logger.info(
                "✅ Created contradiction task %s for session %s (notification_id=%s)",
                task.id,
                session_uuid,
                notification.get("id"),
            )

        logger.info(
            "📊 Scheduler poller summary: %d contradiction notifications, %d tasks created, %d skipped (task already exists)",
            contradiction_count,
            len(results),
            skipped_count,
        )

    return results

