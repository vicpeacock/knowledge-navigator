from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from app.models.notifications import (
    Notification,
    NotificationChannel,
    NotificationPriority,
)

_PRIORITY_ORDER = {
    NotificationPriority.CRITICAL: 50,
    NotificationPriority.HIGH: 40,
    NotificationPriority.MEDIUM: 30,
    NotificationPriority.LOW: 20,
    NotificationPriority.INFO: 10,
}


class NotificationCenter:
    """Lightweight in-memory bus used by agents to exchange notifications."""

    def __init__(self) -> None:
        self._notifications: List[Notification] = []

    # --------------------------------------------------------------------- #
    # Publish helpers
    # --------------------------------------------------------------------- #
    def publish(self, notification: Notification) -> Notification:
        """Register a notification."""

        self._notifications.append(notification)
        return notification

    def publish_many(self, notifications: Iterable[Notification]) -> None:
        for notification in notifications:
            self.publish(notification)

    # --------------------------------------------------------------------- #
    # Queries
    # --------------------------------------------------------------------- #
    def all(self) -> List[Notification]:
        return list(self._notifications)

    def by_min_priority(self, threshold: NotificationPriority) -> List[Notification]:
        min_value = _PRIORITY_ORDER[threshold]
        return [
            notification
            for notification in self._notifications
            if _PRIORITY_ORDER[notification.priority] >= min_value
        ]

    def by_channel(self, channel: NotificationChannel) -> List[Notification]:
        return [
            notification
            for notification in self._notifications
            if notification.channel == channel
        ]

    # --------------------------------------------------------------------- #
    # Serialization helpers
    # --------------------------------------------------------------------- #
    def as_transport(
        self,
        *,
        min_priority: Optional[NotificationPriority] = None,
    ) -> List[Dict[str, object]]:
        if min_priority is None:
            notifications = self._notifications
        else:
            notifications = self.by_min_priority(min_priority)
        return [notification.to_transport_dict() for notification in notifications]

    # --------------------------------------------------------------------- #
    # Maintenance
    # --------------------------------------------------------------------- #
    def clear(self) -> None:
        self._notifications.clear()


