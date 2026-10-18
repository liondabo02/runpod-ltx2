from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from ahos import live_activity
from ahos.autonomous_company import PersistentMissionQueue, QueueStatus
from ahos.mission_orchestrator import WorkItem, WorkerExecutionResult
from ahos.owner_console import build_default_console


@pytest.fixture(autouse=True)
def _reset_live_activity():
    live_activity.reset_for_tests()
    yield
    live_activity.reset_for_tests()


def test_mission_deadline_blocks_long_running_executor(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AHOS_MISSION_TIMEOUT_SECONDS", "0.2")
    monkeypatch.setenv("AHOS_CANCEL_WAIT_SECONDS", "0.2")
    console = build_default_console(tmp_path)
    spec = console.book.active()[0]
    stop = threading.Event()

    def slow(item: WorkItem, worker_id: str) -> WorkerExecutionResult:
        stop.wait(3.0)  # deadline aşılana kadar bekler
        return WorkerExecutionResult(
            task_id=item.task_id,
            worker_id=worker_id,
            success=True,
            summary="geç kaldı",
            artifacts=(),
        )

    started = time.monotonic()
    result = console.run_department_mission(spec, "süre sınırı testi", executor=slow)
    elapsed = time.monotonic() - started
    stop.set()
    time.sleep(0.2)

    assert elapsed < 1.5, f"görev zamanında kesilmedi: {elapsed:.2f}s"
    assert result.status in {"blocked", "error"}
    assert "timeout" in result.message.lower()


def test_queue_survives_restart_and_reclaims_after_lease(tmp_path: Path) -> None:
    path = tmp_path / "queue.db"
    first = PersistentMissionQueue(path)
    first.enqueue(
        mission_id="m-1",
        objective="yeniden başlatma testi",
        primary_department="oyun",
        max_attempts=2,
    )
    claimed = first.claim_next(owner="worker-a", lease_seconds=1)
    assert claimed is not None and claimed.lease_owner == "worker-a"

    # Süreç yeniden başladı: aynı dosya üzerinde yeni kuyruk örneği.
    second = PersistentMissionQueue(path)
    restored = second.get("m-1")
    assert restored is not None
    assert restored.status is QueueStatus.RUNNING
    assert restored.lease_owner == "worker-a"

    # Lease süresi geçti: kurtarılır ve başka sahip tarafından alınabilir.
    recovered = second.recover_expired_leases(now=time.time() + 5)
    assert recovered == 1

    again = second.claim_next(owner="worker-b", lease_seconds=30)
    assert again is not None
    assert again.mission_id == "m-1"
    assert again.lease_owner == "worker-b"
    assert again.attempts == 2


def test_leased_mission_cannot_be_claimed_by_second_owner(tmp_path: Path) -> None:
    queue = PersistentMissionQueue(tmp_path / "queue.db")
    queue.enqueue(
        mission_id="m-2",
        objective="çift sahiplenme testi",
        primary_department="oyun",
    )
    first = queue.claim_next(owner="worker-a", lease_seconds=60)
    second = queue.claim_next(owner="worker-b", lease_seconds=60)

    assert first is not None
    assert second is None
    assert queue.get("m-2").lease_owner == "worker-a"
