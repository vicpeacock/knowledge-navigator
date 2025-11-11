from __future__ import annotations

import asyncio
import copy
import logging
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any, Dict, Optional
from uuid import UUID

from app.core.health_check import HealthCheckService
from app.models.notifications import (
    Notification,
    NotificationChannel,
    NotificationPayload,
    NotificationPriority,
    NotificationSource,
)
from app.services.agent_activity_stream import AgentActivityStream
from app.services.notification_center import NotificationCenter

logger = logging.getLogger(__name__)

# Sentinel session used when broadcasting agent activity events that are not tied to a chat session.
_SYSTEM_SESSION_ID = UUID(int=0)

_PRIORITY_BY_STATUS = {
    "healthy": NotificationPriority.INFO,
    "degraded": NotificationPriority.HIGH,
    "unhealthy": NotificationPriority.CRITICAL,
}


class ServiceHealthAgent:
    """
    Background agent that periodically verifies the health of core services and integrations.

    - Runs the existing HealthCheckService to reuse all probe logic.
    - Emits notifications when a service changes state (healthy ↔ degraded/unhealthy).
    - Tracks consecutive failures to avoid noisy alerts.
    - Publishes telemetry events so UI/monitoring layers can show activity.
    """

    agent_id = "service_health_agent"
    agent_name = "Service Health Agent"

    def __init__(
        self,
        *,
        notification_center: NotificationCenter,
        agent_activity_stream: Optional[AgentActivityStream] = None,
        health_checker: Optional[HealthCheckService] = None,
    ) -> None:
        self._notification_center = notification_center
        self._activity_stream = agent_activity_stream
        self._health_checker = health_checker or HealthCheckService()

        self._last_status: Dict[str, str] = {}
        self._failure_counts: Dict[str, int] = defaultdict(int)
        self._snapshot: Dict[str, Any] = {}
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    async def run_once(self) -> Dict[str, Any]:
        """Execute a full round of health checks and handle state transitions."""

        self._publish_activity("started", "Verifica dello stato dei servizi avviata")

        result = await self._health_checker.check_all_services()
        timestamp = datetime.now(UTC)

        services = result.get("services", {})

        for service_name, service_status in services.items():
            self._handle_service_status(service_name, service_status, timestamp)

        # Persist snapshot for other consumers (planner/UI/tests).
        await self._store_snapshot(result, timestamp)

        healthy_count = sum(
            1 for status in services.values() if status.get("healthy", False)
        )
        summary_message = (
            f"Verifica conclusa ({healthy_count}/{len(services)} servizi operativi)"
        )
        self._publish_activity("completed", summary_message)

        return result

    async def get_snapshot(self) -> Dict[str, Any]:
        """Return the latest health snapshot (deep copy)."""
        async with self._lock:
            snapshot = copy.deepcopy(self._snapshot)

        if not snapshot:
            return {}

        if isinstance(snapshot.get("checked_at"), datetime):
            snapshot["checked_at"] = snapshot["checked_at"].isoformat()

        for service in snapshot.get("services", {}).values():
            if isinstance(service.get("checked_at"), datetime):
                service["checked_at"] = service["checked_at"].isoformat()

        return snapshot

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _handle_service_status(
        self,
        service_name: str,
        status: Dict[str, Any],
        timestamp: datetime,
    ) -> None:
        healthy = bool(status.get("healthy"))
        mandatory = bool(status.get("mandatory"))

        status_label = self._determine_status_label(healthy, mandatory)

        # Update failure counters.
        if healthy:
            self._failure_counts[service_name] = 0
        else:
            self._failure_counts[service_name] += 1

        previous_status = self._last_status.get(service_name)

        # Emit notifications only when the status changes.
        if status_label != previous_status:
            # Avoid spamming on initial healthy state.
            if not (previous_status is None and status_label == "healthy"):
                self._emit_notification(
                    service_name=service_name,
                    status_label=status_label,
                    status=status,
                    timestamp=timestamp,
                    consecutive_failures=self._failure_counts[service_name],
                )

        self._last_status[service_name] = status_label

    async def _store_snapshot(self, result: Dict[str, Any], timestamp: datetime) -> None:
        async with self._lock:
            services_snapshot: Dict[str, Any] = {}
            for name, status in result.get("services", {}).items():
                healthy = bool(status.get("healthy"))
                mandatory = bool(status.get("mandatory"))
                status_label = self._determine_status_label(healthy, mandatory)

                services_snapshot[name] = {
                    "status": status_label,
                    "healthy": healthy,
                    "mandatory": mandatory,
                    "message": status.get("message"),
                    "error": status.get("error"),
                    "latency_ms": status.get("latency_ms"),
                    "checked_at": timestamp,
                    "consecutive_failures": self._failure_counts[name],
                }

            self._snapshot = {
                "checked_at": timestamp,
                "all_healthy": result.get("all_healthy"),
                "all_mandatory_healthy": result.get("all_mandatory_healthy"),
                "services": services_snapshot,
                "unhealthy_services": result.get("unhealthy_services", []),
                "unhealthy_mandatory_services": result.get(
                    "unhealthy_mandatory_services", []
                ),
            }

    def _emit_notification(
        self,
        *,
        service_name: str,
        status_label: str,
        status: Dict[str, Any],
        timestamp: datetime,
        consecutive_failures: int,
    ) -> None:
        priority = _PRIORITY_BY_STATUS[status_label]
        channel = (
            NotificationChannel.ASYNC
            if status_label == "healthy"
            else NotificationChannel.IMMEDIATE
        )

        error_message = status.get("error") or status.get("message")
        if status_label == "healthy":
            message = f"Servizio '{service_name}' tornato operativo."
        else:
            base = (
                f"Servizio '{service_name}' {status_label}. "
                "Verificare lo stato e i log di sistema."
            )
            if error_message:
                base = f"{base} Dettagli: {error_message}"
            message = base

        notification = Notification(
            type="service_health",
            priority=priority,
            channel=channel,
            source=NotificationSource(agent=self.agent_id, feature=service_name),
            payload=NotificationPayload(
                title="Service Health Update",
                message=message,
                summary=status_label,
                data={
                    "service": service_name,
                    "status": status_label,
                    "healthy": bool(status.get("healthy")),
                    "mandatory": bool(status.get("mandatory")),
                    "error": status.get("error"),
                    "message": status.get("message"),
                    "checked_at": timestamp.isoformat(),
                    "consecutive_failures": consecutive_failures,
                },
            ),
            tags=["service_health", service_name],
        )

        self._notification_center.publish(notification)

        logger.info(
            "[ServiceHealthAgent] %s -> %s (priority=%s, failures=%d)",
            service_name,
            status_label,
            priority.value,
            consecutive_failures,
        )

        self._publish_activity(
            "warning" if status_label != "healthy" else "info",
            message,
            extra={
                "service": service_name,
                "status": status_label,
                "priority": priority.value,
                "consecutive_failures": consecutive_failures,
            },
        )

    def _publish_activity(
        self, status: str, message: str, extra: Optional[Dict[str, Any]] = None
    ) -> None:
        if not self._activity_stream:
            return

        event = {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "status": status,
            "timestamp": datetime.now(UTC),
            "message": message,
        }
        if extra:
            event.update(extra)

        try:
            self._activity_stream.publish(_SYSTEM_SESSION_ID, event)
        except Exception:
            logger.debug(
                "Unable to publish service health telemetry event", exc_info=True
            )

    @staticmethod
    def _determine_status_label(healthy: bool, mandatory: bool) -> str:
        if healthy:
            return "healthy"
        return "unhealthy" if mandatory else "degraded"


