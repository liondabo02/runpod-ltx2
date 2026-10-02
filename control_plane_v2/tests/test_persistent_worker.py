from __future__ import annotations

import asyncio
import time

import pytest

from miniverse.queue import SQLiteTaskQueue
from miniverse.worker import PersistentWorker


class SuccessExecutor:
    async def execute(self, task):
        await asyncio.sleep(0.02)
        return {"ok": True, "task_id": task.id}


class FlakyExecutor:
    def __init__(self):
        self.calls = 0

    async def execute(self, task):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("temporary failure")
        return {"ok": True, "attempt": self.calls}


@pytest.mark.asyncio
async def test_worker_completes_task(tmp_path):
    queue = SQLiteTaskQueue(tmp_path / "queue.db")
    task_id = queue.enqueue("coding", {"task": "x", "workspace": "/tmp"})
    worker = PersistentWorker(
        queue,
        SuccessExecutor(),
        owner="test-worker",
        lease_seconds=1.0,
        heartbeat_seconds=0.1,
        retry_base_seconds=0,
        poll_seconds=0.01,
    )

    assert await worker.run_once() is True
    record = queue.get(task_id)
    assert record is not None
    assert record.status == "completed"
    assert record.attempts == 1
    assert record.result == {"ok": True, "task_id": task_id}


@pytest.mark.asyncio
async def test_worker_retries_then_completes(tmp_path):
    queue = SQLiteTaskQueue(tmp_path / "queue.db")
    task_id = queue.enqueue("coding", {"task": "x", "workspace": "/tmp"}, max_attempts=3)
    executor = FlakyExecutor()
    worker = PersistentWorker(
        queue,
        executor,
        owner="retry-worker",
        lease_seconds=1.0,
        heartbeat_seconds=0.1,
        retry_base_seconds=0,
        poll_seconds=0.01,
    )

    assert await worker.run_once() is True
    first = queue.get(task_id)
    assert first is not None
    assert first.status == "pending"
    assert first.attempts == 1
    assert "temporary failure" in (first.last_error or "")

    assert await worker.run_once() is True
    final = queue.get(task_id)
    assert final is not None
    assert final.status == "completed"
    assert final.attempts == 2
    assert final.result == {"ok": True, "attempt": 2}


def test_expired_lease_is_reclaimed(tmp_path):
    queue = SQLiteTaskQueue(tmp_path / "queue.db")
    task_id = queue.enqueue("coding", {"task": "x", "workspace": "/tmp"})
    first = queue.claim("worker-a", lease_seconds=0.01)
    assert first is not None
    time.sleep(0.02)

    second = queue.claim("worker-b", lease_seconds=1.0)
    assert second is not None
    assert second.id == task_id
    assert second.lease_owner == "worker-b"
    assert second.attempts == 2


def test_wrong_owner_cannot_complete(tmp_path):
    queue = SQLiteTaskQueue(tmp_path / "queue.db")
    task_id = queue.enqueue("coding", {"task": "x", "workspace": "/tmp"})
    claimed = queue.claim("worker-a", lease_seconds=1.0)
    assert claimed is not None
    assert queue.complete(task_id, "worker-b", {"ok": True}) is False
    assert queue.get(task_id).status == "running"
