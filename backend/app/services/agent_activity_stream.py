from __future__ import annotations

import asyncio
import json
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Deque, Dict, List, MutableSet, Optional
from uuid import UUID


@dataclass(frozen=True)
class _Subscriber:
    """Representation of a subscriber queue for cleanup purposes."""

    queue: asyncio.Queue


class AgentActivityStream:
    """
    In-memory broker that fans out agent activity telemetry events to subscribers.

    - Maintains a bounded history per session so newcomers can replay recent events.
    - Uses asyncio.Queue per subscriber to avoid blocking producers.
    - Designed to be lightweight until we adopt a persistent/event sourcing backend.
    """

    def __init__(self, history_size: int = 200, queue_size: int = 100) -> None:
        self._history_size = max(1, history_size)
        self._queue_size = max(1, queue_size)
        self._history: Dict[UUID, Deque[Dict[str, Any]]] = defaultdict(deque)
        self._subscribers: Dict[UUID, MutableSet[_Subscriber]] = defaultdict(set)
        self._lock = asyncio.Lock()

    @staticmethod
    def _serialize_event(event: Dict[str, Any]) -> Dict[str, Any]:
        """Return a JSON-serialisable copy of the telemetry event."""
        serialised = dict(event)
        timestamp = serialised.get("timestamp")
        if isinstance(timestamp, datetime):
            serialised["timestamp"] = timestamp.isoformat()
        return serialised

    async def register(self, session_id: UUID) -> asyncio.Queue:
        """
        Register a new subscriber for the given session.
        Returns the queue that will receive telemetry events.
        """
        queue: asyncio.Queue = asyncio.Queue(maxsize=self._queue_size)
        subscriber = _Subscriber(queue=queue)
        async with self._lock:
            self._subscribers[session_id].add(subscriber)
        return queue

    async def unregister(self, session_id: UUID, queue: asyncio.Queue) -> None:
        """Remove a subscriber queue when the client disconnects."""
        subscriber = _Subscriber(queue=queue)
        async with self._lock:
            subscribers = self._subscribers.get(session_id)
            if subscribers and subscriber in subscribers:
                subscribers.remove(subscriber)
                if not subscribers:
                    self._subscribers.pop(session_id, None)

    def publish(self, session_id: UUID, event: Dict[str, Any]) -> None:
        """Publish a new telemetry event to all subscribers."""
        serialised = self._serialize_event(event)
        history = self._history[session_id]
        history.append(serialised)
        while len(history) > self._history_size:
            history.popleft()

        subscribers = list(self._subscribers.get(session_id, []))
        if not subscribers:
            return

        for subscriber in subscribers:
            queue = subscriber.queue
            try:
                queue.put_nowait(serialised)
            except asyncio.QueueFull:
                # Drop the oldest pending event to make room for the newest one.
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    queue.put_nowait(serialised)
                except asyncio.QueueFull:
                    # Give up if queue is still full.
                    continue

    def snapshot(self, session_id: UUID) -> List[Dict[str, Any]]:
        """Return the current history snapshot for the session."""
        return list(self._history.get(session_id, []))

    def as_sse_payload(self, event: Dict[str, Any], event_type: str = "agent_activity") -> str:
        """Format a telemetry event for Server-Sent Events."""
        payload = {
            "type": event_type,
            "event": event,
        }
        return f"data: {json.dumps(payload)}\n\n"

    def snapshot_sse_payload(self, session_id: UUID) -> Optional[str]:
        """Create an SSE payload containing the current snapshot."""
        history = self.snapshot(session_id)
        if not history:
            return None
        payload = {
            "type": "agent_activity_snapshot",
            "events": history,
        }
        return f"data: {json.dumps(payload)}\n\n"


