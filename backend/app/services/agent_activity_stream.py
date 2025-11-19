from __future__ import annotations

import asyncio
import json
import threading
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
        self._async_lock = asyncio.Lock()  # Per register/unregister (async)
        self._sync_lock = threading.Lock()  # Per publish/get_active_sessions (sync)

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
        async with self._async_lock:
            with self._sync_lock:
                self._subscribers[session_id].add(subscriber)
        return queue

    async def unregister(self, session_id: UUID, queue: asyncio.Queue) -> None:
        """Remove a subscriber queue when the client disconnects."""
        subscriber = _Subscriber(queue=queue)
        async with self._async_lock:
            with self._sync_lock:
                subscribers = self._subscribers.get(session_id)
                if subscribers and subscriber in subscribers:
                    subscribers.remove(subscriber)
                    if not subscribers:
                        self._subscribers.pop(session_id, None)

    def publish(self, session_id: UUID, event: Dict[str, Any]) -> None:
        """Publish a new telemetry event to all subscribers."""
        import logging
        logger = logging.getLogger(__name__)
        
        serialised = self._serialize_event(event)
        history = self._history[session_id]
        history.append(serialised)
        while len(history) > self._history_size:
            history.popleft()

        # Make a thread-safe copy of subscribers list
        with self._sync_lock:
            subscribers = list(self._subscribers.get(session_id, []))
            all_sessions = list(self._subscribers.keys())
        
        # event is a dict (serialized), not a Pydantic model
        agent_id = event.get('agent_id', 'unknown') if isinstance(event, dict) else getattr(event, 'agent_id', 'unknown')
        status = event.get('status', 'unknown') if isinstance(event, dict) else getattr(event, 'status', 'unknown')
        
        if not subscribers:
            logger.warning(f"⚠️  No subscribers for session {session_id}. Event will not be delivered: {agent_id} ({status}). Active sessions: {all_sessions}")
            return
        
        logger.info(f"📡 Publishing event to {len(subscribers)} subscriber(s) for session {session_id}: {agent_id} ({status})")

        # Process subscribers outside the lock to avoid blocking
        events_sent = 0
        for subscriber in subscribers:
            queue = subscriber.queue
            try:
                queue.put_nowait(serialised)
                events_sent += 1
            except asyncio.QueueFull:
                # Drop the oldest pending event to make room for the newest one.
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    queue.put_nowait(serialised)
                    events_sent += 1
                except asyncio.QueueFull:
                    # Give up if queue is still full.
                    logger.warning(f"⚠️  Queue full for subscriber, dropping event: {agent_id} ({status})")
                    continue
        
        if events_sent > 0:
            logger.debug(f"✅ Successfully sent event to {events_sent}/{len(subscribers)} subscribers: {agent_id} ({status})")
        else:
            logger.warning(f"⚠️  Failed to send event to any subscriber: {agent_id} ({status})")

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
    
    def get_active_sessions(self) -> List[UUID]:
        """Return list of session IDs that have active subscribers."""
        with self._sync_lock:
            return list(self._subscribers.keys())
    
    def publish_to_all_active_sessions(self, event: Dict[str, Any]) -> None:
        """Publish an event to all sessions with active subscribers."""
        # Get a snapshot of active sessions to avoid holding lock during publish
        with self._sync_lock:
            active_sessions = list(self._subscribers.keys())
        
        if not active_sessions:
            return
        
        # Publish to each session (publish() will acquire its own lock)
        for session_id in active_sessions:
            self.publish(session_id, event)


