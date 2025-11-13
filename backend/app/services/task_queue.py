from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Callable
from uuid import UUID, uuid4


class TaskPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TaskStatus(str, Enum):
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    WAITING_USER = "waiting_user"
    COMPLETED = "completed"
    FAILED = "failed"


_PRIORITY_ORDER = {
    TaskPriority.CRITICAL: 4,
    TaskPriority.HIGH: 3,
    TaskPriority.MEDIUM: 2,
    TaskPriority.LOW: 1,
}


@dataclass
class Task:
    type: str
    payload: Dict[str, Any]
    origin: str
    priority: TaskPriority = TaskPriority.MEDIUM
    id: str = field(default_factory=lambda: str(uuid4()))
    status: TaskStatus = TaskStatus.QUEUED
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "priority": self.priority.value,
            "origin": self.origin,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "payload": self.payload,
        }


class TaskQueue:
    """
    In-memory priority queue for inter-agent coordination.

    Tasks are stored per session and selected by priority + FIFO order.
    """

    def __init__(self) -> None:
        self._tasks: Dict[UUID, Dict[str, Task]] = {}

    def iter_tasks(self, session_id: UUID) -> Iterable[Task]:
        return self._tasks.get(session_id, {}).values()

    def enqueue(self, session_id: UUID, task: Task) -> Task:
        session_tasks = self._tasks.setdefault(session_id, {})
        session_tasks[task.id] = task
        return task

    def list_tasks(self, session_id: UUID) -> List[Task]:
        return list(self._tasks.get(session_id, {}).values())

    def find_task_by_status(
        self, session_id: UUID, status: TaskStatus
    ) -> Optional[Task]:
        session_tasks = self._tasks.get(session_id)
        if not session_tasks:
            return None

        candidates = [
            task for task in session_tasks.values() if task.status == status
        ]
        if not candidates:
            return None

        candidates.sort(
            key=lambda task: (
                -_PRIORITY_ORDER.get(task.priority, 0),
                task.created_at,
            )
        )
        return candidates[0]

    def find_task_by_type(
        self,
        session_id: UUID,
        task_type: str,
        statuses: Optional[Iterable[TaskStatus]] = None,
    ) -> Optional[Task]:
        session_tasks = self._tasks.get(session_id)
        if not session_tasks:
            return None

        statuses_set = set(statuses) if statuses else None

        for task in session_tasks.values():
            if task.type != task_type:
                continue
            if statuses_set and task.status not in statuses_set:
                continue
            return task
        return None

    def task_exists(
        self,
        session_id: UUID,
        task_type: str,
        statuses: Optional[Iterable[TaskStatus]] = None,
    ) -> bool:
        return (
            self.find_task_by_type(session_id, task_type, statuses=statuses) is not None
        )

    def start_next(self, session_id: UUID) -> Optional[Task]:
        session_tasks = self._tasks.get(session_id)
        if not session_tasks:
            return None

        queued = [
            task for task in session_tasks.values() if task.status == TaskStatus.QUEUED
        ]
        if not queued:
            return None

        queued.sort(
            key=lambda task: (
                -_PRIORITY_ORDER.get(task.priority, 0),
                task.created_at,
            )
        )
        next_task = queued[0]
        next_task.status = TaskStatus.IN_PROGRESS
        next_task.updated_at = datetime.now(UTC)
        return next_task

    def get_task(self, session_id: UUID, task_id: str) -> Optional[Task]:
        return self._tasks.get(session_id, {}).get(task_id)

    def update_task(
        self,
        session_id: UUID,
        task_id: str,
        *,
        status: Optional[TaskStatus] = None,
        payload_updates: Optional[Dict[str, Any]] = None,
    ) -> Optional[Task]:
        task = self.get_task(session_id, task_id)
        if not task:
            return None

        if status:
            task.status = status
        if payload_updates:
            task.payload.update(payload_updates)

        task.updated_at = datetime.now(UTC)
        return task

    def complete_task(
        self,
        session_id: UUID,
        task_id: str,
        *,
        payload_updates: Optional[Dict[str, Any]] = None,
    ) -> Optional[Task]:
        return self.update_task(
            session_id,
            task_id,
            status=TaskStatus.COMPLETED,
            payload_updates=payload_updates,
        )

    def clear_completed(self, session_id: UUID) -> None:
        session_tasks = self._tasks.get(session_id)
        if not session_tasks:
            return
        remaining = {
            task_id: task
            for task_id, task in session_tasks.items()
            if task.status != TaskStatus.COMPLETED
        }
        self._tasks[session_id] = remaining


