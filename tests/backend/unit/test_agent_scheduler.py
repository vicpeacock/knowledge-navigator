from datetime import datetime, UTC
from uuid import uuid4

import pytest

from app.services.agent_scheduler import AgentScheduler, ScheduledAgent
from app.services.task_queue import TaskQueue, Task, TaskPriority


@pytest.mark.asyncio
async def test_agent_scheduler_enqueues_tasks() -> None:
    queue = TaskQueue()
    session_id = uuid4()

    produced = {"count": 0}

    async def poller():
        if produced["count"] > 0:
            return []
        produced["count"] += 1
        task = Task(
            type="example",
            origin="test_agent",
            priority=TaskPriority.MEDIUM,
            payload={"value": 1},
        )
        return [(session_id, task)]

    dispatcher_calls = []

    class FakeDispatcher:
        def schedule_dispatch(self, sid):
            dispatcher_calls.append(sid)

    scheduler = AgentScheduler(task_queue=queue, tick_seconds=5)
    scheduler.register_dispatcher(FakeDispatcher())
    agent = ScheduledAgent(
        name="example",
        interval_seconds=1,
        poller=poller,
        last_run=datetime.fromtimestamp(0, tz=UTC),
    )
    scheduler.register_agent(agent)

    # Access the protected method for unit test purposes
    await scheduler._poll_agents()  # type: ignore[attr-defined]

    tasks = queue.list_tasks(session_id)
    assert len(tasks) == 1
    assert tasks[0].payload["value"] == 1
    assert dispatcher_calls == [session_id]

