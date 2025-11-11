import asyncio
from datetime import datetime

import pytest

from app.models.notifications import NotificationPriority
from app.services.notification_center import NotificationCenter
from app.services.service_health_agent import ServiceHealthAgent

pytestmark = pytest.mark.asyncio


class FakeHealthChecker:
    def __init__(self, result):
        self.result = result
        self.calls = 0

    async def check_all_services(self):
        await asyncio.sleep(0)  # ensure async behaviour
        self.calls += 1
        return self.result


def _base_result():
    return {
        "all_healthy": True,
        "all_mandatory_healthy": True,
        "services": {
            "postgres": {
                "healthy": True,
                "mandatory": True,
                "message": "OK",
            }
        },
        "unhealthy_services": [],
        "unhealthy_mandatory_services": [],
    }


async def test_service_health_agent_emits_notifications_on_status_change():
    notification_center = NotificationCenter()
    checker = FakeHealthChecker(_base_result())
    agent = ServiceHealthAgent(
        notification_center=notification_center,
        agent_activity_stream=None,
        health_checker=checker,
    )

    # First run with healthy services should not emit notifications
    await agent.run_once()
    assert notification_center.all() == []

    # Simulate failure of mandatory service
    checker.result = {
        "all_healthy": False,
        "all_mandatory_healthy": False,
        "services": {
            "postgres": {
                "healthy": False,
                "mandatory": True,
                "error": "connection refused",
            }
        },
        "unhealthy_services": [
            {"service": "postgres", "healthy": False, "mandatory": True}
        ],
        "unhealthy_mandatory_services": [
            {"service": "postgres", "healthy": False, "mandatory": True}
        ],
    }

    await agent.run_once()

    notifications = notification_center.all()
    assert len(notifications) == 1
    notif = notifications[0]
    assert notif.priority == NotificationPriority.CRITICAL
    assert notif.payload.data["service"] == "postgres"
    assert notif.payload.data["status"] == "unhealthy"
    assert notif.payload.data["consecutive_failures"] == 1
    assert notif.payload.data["error"] == "connection refused"

    # Recovery path emits INFO notification
    checker.result = _base_result()
    await agent.run_once()
    notifications = notification_center.all()
    assert len(notifications) == 2
    recovery = notifications[-1]
    assert recovery.priority == NotificationPriority.INFO
    assert recovery.payload.data["status"] == "healthy"


async def test_service_health_agent_snapshot_contains_last_result():
    notification_center = NotificationCenter()
    checker = FakeHealthChecker(_base_result())
    agent = ServiceHealthAgent(
        notification_center=notification_center,
        agent_activity_stream=None,
        health_checker=checker,
    )

    await agent.run_once()
    snapshot = await agent.get_snapshot()
    assert snapshot["all_healthy"] is True
    assert "postgres" in snapshot["services"]
    svc = snapshot["services"]["postgres"]
    assert svc["status"] == "healthy"
    assert svc["mandatory"] is True
    assert isinstance(datetime.fromisoformat(snapshot["checked_at"]), datetime)

