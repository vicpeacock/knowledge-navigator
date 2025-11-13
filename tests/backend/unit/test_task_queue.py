from uuid import uuid4

from app.services.task_queue import TaskQueue, Task, TaskPriority, TaskStatus


def test_task_queue_orders_by_priority_and_fifo() -> None:
    session_id = uuid4()
    queue = TaskQueue()

    low = Task(type="test", payload={}, origin="agent_low", priority=TaskPriority.LOW)
    high = Task(type="test", payload={}, origin="agent_high", priority=TaskPriority.HIGH)
    medium = Task(type="test", payload={}, origin="agent_medium", priority=TaskPriority.MEDIUM)

    queue.enqueue(session_id, low)
    queue.enqueue(session_id, high)
    queue.enqueue(session_id, medium)

    first = queue.start_next(session_id)
    assert first is high
    assert first.status == TaskStatus.IN_PROGRESS
    queue.update_task(session_id, first.id, status=TaskStatus.WAITING_USER)

    second = queue.start_next(session_id)
    assert second is medium
    third = queue.start_next(session_id)
    assert third is low
    assert queue.start_next(session_id) is None


def test_update_and_complete_task() -> None:
    session_id = uuid4()
    queue = TaskQueue()

    task = Task(type="example", payload={"count": 1}, origin="agent")
    queue.enqueue(session_id, task)

    started = queue.start_next(session_id)
    assert started is task
    queue.update_task(
        session_id,
        task.id,
        status=TaskStatus.WAITING_USER,
        payload_updates={"note": "pending"},
    )

    refreshed = queue.get_task(session_id, task.id)
    assert refreshed is task
    assert refreshed.status == TaskStatus.WAITING_USER
    assert refreshed.payload["note"] == "pending"

    queue.complete_task(
        session_id,
        task.id,
        payload_updates={"result": "ok"},
    )
    assert task.status == TaskStatus.COMPLETED
    assert task.payload["result"] == "ok"

    queue.clear_completed(session_id)
    assert queue.list_tasks(session_id) == []


def test_find_task_by_status() -> None:
    session_id = uuid4()
    queue = TaskQueue()

    t1 = Task(type="example", payload={}, origin="a", priority=TaskPriority.HIGH)
    t2 = Task(type="example", payload={}, origin="b", priority=TaskPriority.MEDIUM)
    queue.enqueue(session_id, t1)
    queue.enqueue(session_id, t2)

    queue.update_task(session_id, t1.id, status=TaskStatus.WAITING_USER)
    queue.update_task(session_id, t2.id, status=TaskStatus.WAITING_USER)

    found_status = queue.find_task_by_status(session_id, TaskStatus.WAITING_USER)
    assert found_status is t1  # highest priority first

    found_type = queue.find_task_by_type(session_id, "example")
    assert found_type is t1
    assert queue.task_exists(session_id, "example")
    assert not queue.task_exists(session_id, "nonexistent")

