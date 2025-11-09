from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class NotificationPriority(str, Enum):
    """Priority associated with a notification event."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class NotificationChannel(str, Enum):
    """Suggested delivery channel for a notification."""

    BLOCKING = "blocking"  # Must interrupt the UI flow
    IMMEDIATE = "immediate"  # Show in the active session feed
    ASYNC = "async"  # Store in inbox / backlog
    DIGEST = "digest"  # Aggregate in periodic summaries
    LOG = "log"  # Internal logging only


class NotificationSource(BaseModel):
    """Origin of a notification."""

    agent: str = Field(..., description="Agent or service that produced the notification.")
    feature: Optional[str] = Field(
        default=None, description="Specific component/feature within the agent."
    )
    reference_id: Optional[str] = Field(
        default=None, description="External identifier related to the notification."
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)


class NotificationAction(BaseModel):
    """Suggested follow-up action for the notification recipient."""

    id: str
    title: str
    description: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    requires_confirmation: bool = False


class NotificationPayload(BaseModel):
    """Human facing content for the notification."""

    message: str
    title: Optional[str] = None
    summary: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)
    actions: List[NotificationAction] = Field(default_factory=list)


class Notification(BaseModel):
    """Canonical notification envelope shared across agents."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    type: str = Field(..., description="Domain specific type identifier.")
    priority: NotificationPriority = NotificationPriority.MEDIUM
    channel: NotificationChannel = NotificationChannel.IMMEDIATE
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: Optional[datetime] = None
    tags: List[str] = Field(default_factory=list)
    source: NotificationSource
    payload: NotificationPayload

    def to_transport_dict(self) -> Dict[str, Any]:
        """Serialize the notification for transport (e.g. websocket/UI)."""

        document = self.model_dump()
        document["created_at"] = self.created_at.isoformat()
        if self.expires_at is not None:
            document["expires_at"] = self.expires_at.isoformat()
        # Backward compatible payload for existing UI/tests
        content = dict(self.payload.data)
        if "message" not in content:
            content["message"] = self.payload.message
        if self.payload.title and "title" not in content:
            content["title"] = self.payload.title
        if self.payload.summary and "summary" not in content:
            content["summary"] = self.payload.summary
        if self.payload.actions:
            content["actions"] = [action.model_dump() for action in self.payload.actions]
        document["content"] = content
        document["urgency"] = self.priority.value
        return document


