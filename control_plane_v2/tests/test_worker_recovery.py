"""Zero-network regressions for interrupted workers and diagnostic handoff."""
import asyncio
import threading
from dataclasses import dataclass, replace
from types import SimpleNamespace

import pytest

from miniverse.config import Settings
from miniverse.queue import SQLiteTaskQueue
from miniverse.worker import PersistentWorker, PipelineTaskExecutor


@pytest.fixture
def clock(monkeypatch):
    value = [1000.0]
    monkeypatch.setattr('miniverse.queue.time.time', lambda: value[0])
    return value


def test_final_attempt_crash_becomes_failed_and_next_task_runs(tmp_path, clock):
    queue = SQLiteTaskQueue(tmp_path / 'queue.db')
    exhausted = queue.enqueue('coding', {}, max_attempts=1)
    queue.claim('dead-worker', lease_seconds=1)
    next_id = queue.enqueue('coding', {})
    clock[0] += 2
    assert queue.claim('replacement').id == next_id
    record = queue.get(exhausted)
    assert record.status == 'failed'
    assert record.lease_owner is None
    assert 'final attempt' in record.last_error


def test_final_attempt_is_not_reaped_while_lease_is_valid(tmp_path, clock):
    queue = SQLiteTaskQueue(tmp_path / 'queue.db')
    task_id = queue.enqueue('coding', {}, max_attempts=1)
    queue.claim('live', lease_seconds=10)
    assert queue.claim('other') is None
    assert queue.get(task_id).status == 'running'


def test_expired_worker_cannot_renew_complete_or_reschedule(tmp_path, clock):
    queue = SQLiteTaskQueue(tmp_path / 'queue.db')
    task_id = queue.enqueue('coding', {})
    queue.claim('old', lease_seconds=1)
    clock[0] += 2
    assert not queue.heartbeat(task_id, 'old')
    assert not queue.complete(task_id, 'old', {'wrong': True})
    assert not queue.fail(task_id, 'old', 'stale error')
    assert queue.claim('new').attempts == 2
    assert not queue.complete(task_id, 'old', {})


def test_attempt_fences_reused_owner_name(tmp_path, clock):
    queue = SQLiteTaskQueue(tmp_path / 'queue.db')
    task_id = queue.enqueue('coding', {})
    first = queue.claim('same-name', lease_seconds=1)
    clock[0] += 2
    second = queue.claim('same-name', lease_seconds=10)
    assert not queue.heartbeat(task_id, 'same-name', attempt=first.attempts)
    assert not queue.complete(task_id, 'same-name', {}, attempt=first.attempts)
    assert not queue.fail(task_id, 'same-name', 'old', attempt=first.attempts)
    assert queue.complete(task_id, 'same-name', {'ok': True}, attempt=second.attempts)


def test_lease_is_rechecked_after_waiting_for_database_lock(tmp_path, monkeypatch, clock):
    queue = SQLiteTaskQueue(tmp_path / 'queue.db')
    task_id = queue.enqueue('coding', {})
    queue.claim('worker', lease_seconds=1)
    connect = queue._connect
    waiting = threading.Event()
    result = []
    class Connection:
        def __init__(self):
            self.raw = connect()
        def __enter__(self):
            self.raw.__enter__()
            return self
        def __exit__(self, *args):
            return self.raw.__exit__(*args)
        def execute(self, sql, *args):
            if sql.lstrip().startswith(('BEGIN IMMEDIATE', 'UPDATE tasks')):
                waiting.set()
            return self.raw.execute(sql, *args)
    with connect() as lock:
        lock.execute('BEGIN IMMEDIATE')
        monkeypatch.setattr(queue, '_connect', Connection)
        thread = threading.Thread(target=lambda: result.append(queue.complete(task_id, 'worker', {})))
        thread.start()
        try:
            assert waiting.wait(2), 'Completion did not reach the database'
            clock[0] += 2
        finally:
            lock.execute('COMMIT')
            thread.join(2)
    assert not thread.is_alive()
    assert result == [False]


def test_heartbeat_loss_cancels_cooperative_executor(tmp_path, monkeypatch):
    async def scenario():
        queue = SQLiteTaskQueue(tmp_path / 'queue.db')
        task_id = queue.enqueue('coding', {})
        cancelled = asyncio.Event()
        class Executor:
            async def execute(self, task):
                try:
                    await asyncio.Event().wait()
                finally:
                    cancelled.set()
        monkeypatch.setattr(queue, 'heartbeat', lambda *args, **kwargs: False)
        worker = PersistentWorker(queue, Executor(), lease_seconds=2, heartbeat_seconds=.01)
        assert await asyncio.wait_for(worker.run_once(), timeout=1)
        assert cancelled.is_set()
        record = queue.get(task_id)
        assert record.status == 'pending'
        assert 'Lost lease' in record.last_error
        assert record.result is None
    asyncio.run(scenario())


def test_replacement_lease_is_not_overwritten(tmp_path, monkeypatch, clock):
    async def scenario():
        queue = SQLiteTaskQueue(tmp_path / 'queue.db')
        task_id = queue.enqueue('coding', {})
        class Executor:
            async def execute(self, task):
                await asyncio.Event().wait()
        def takeover(*args, **kwargs):
            clock[0] += 5
            assert queue.claim('replacement').id == task_id
            return False
        monkeypatch.setattr(queue, 'heartbeat', takeover)
        worker = PersistentWorker(queue, Executor(), owner='old', lease_seconds=2, heartbeat_seconds=.01)
        await asyncio.wait_for(worker.run_once(), timeout=1)
        record = queue.get(task_id)
        assert record.status == 'running' and record.lease_owner == 'replacement'
        assert record.attempts == 2 and record.last_error is None
    asyncio.run(scenario())


def test_heartbeat_exception_is_observed_and_retried(tmp_path, monkeypatch):
    async def scenario():
        queue = SQLiteTaskQueue(tmp_path / 'queue.db')
        task_id = queue.enqueue('coding', {})
        class Executor:
            async def execute(self, task):
                await asyncio.Event().wait()
        def unavailable(*args, **kwargs):
            raise RuntimeError('heartbeat storage unavailable')
        monkeypatch.setattr(queue, 'heartbeat', unavailable)
        worker = PersistentWorker(queue, Executor(), lease_seconds=2, heartbeat_seconds=.01)
        await asyncio.wait_for(worker.run_once(), timeout=1)
        assert 'heartbeat storage unavailable' in queue.get(task_id).last_error
        assert queue.get(task_id).status == 'pending'
    asyncio.run(scenario())


def test_worker_cancellation_cleans_up_async_executor(tmp_path):
    async def scenario():
        queue = SQLiteTaskQueue(tmp_path / 'queue.db')
        task_id = queue.enqueue('coding', {})
        started, cancelled = asyncio.Event(), asyncio.Event()
        class Executor:
            async def execute(self, task):
                started.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    cancelled.set()
        worker = PersistentWorker(queue, Executor(), lease_seconds=2, heartbeat_seconds=.1)
        run = asyncio.create_task(worker.run_once())
        await started.wait()
        run.cancel()
        with pytest.raises(asyncio.CancelledError):
            await run
        assert cancelled.is_set()
        # Recovery is left to lease expiry, not a false completion.
        assert queue.get(task_id).status == 'running'
    asyncio.run(scenario())


def test_retry_handoff_includes_bounded_error_and_existing_workspace(tmp_path):
    async def scenario():
        queue = SQLiteTaskQueue(tmp_path / 'queue.db')
        task_id = queue.enqueue('coding', {'task': 'implement feature', 'workspace': str(tmp_path)})
        first = queue.claim('first')
        queue.fail(task_id, 'first', 'assertion failed: expected 42 ' + 'x' * 7000)
        retry = queue.claim('second')
        calls = []
        @dataclass
        class Builder:
            summary: str = 'fixed'
        class Pipeline:
            async def execute(self, instruction, workspace):
                calls.append((instruction, workspace))
                return SimpleNamespace(task=instruction, preflight_report='local', builder=Builder(),
                    qa_report='tested', owner_approval_required=False, owner_approval_reasons=())
        executor = PipelineTaskExecutor(pipeline=Pipeline())
        await executor.execute(retry)
        instruction, workspace = calls[0]
        assert 'attempt 2/3' in instruction and 'expected 42' in instruction
        assert 'existing isolated workspace' in instruction and 'untrusted diagnostic' in instruction
        assert len(instruction) < 4600 and workspace == tmp_path
        calls.clear()
        await executor.execute(replace(first, last_error=None))
        assert calls[0][0] == 'implement feature'
    asyncio.run(scenario())


@pytest.mark.parametrize('value', [0, 501, -1, True, 1.5])
def test_invalid_builder_iteration_limits_rejected(value):
    with pytest.raises(ValueError, match='MAX_ITERATIONS'):
        Settings(openhands_max_iterations=value)


def test_builder_iteration_limit_can_be_configured_without_changing_budget():
    config = Settings(openhands_max_iterations=64)
    assert config.openhands_max_iterations == 64
    assert config.max_budget_per_run_usd == Settings().max_budget_per_run_usd
