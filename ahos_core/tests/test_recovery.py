from __future__ import annotations

import time

from ahos.autonomous_company import PersistentMissionQueue, QueueStatus
from ahos.recovery import recover


def test_expired_lease_is_recovered_and_mission_rerunnable(tmp_path) -> None:
    queue = PersistentMissionQueue(tmp_path / "q.db")
    queue.enqueue(
        mission_id="m-crash",
        objective="çöken görev",
        primary_department="oyun",
        max_attempts=2,
    )
    claimed = queue.claim_next(owner="worker-a", lease_seconds=1)
    assert claimed is not None

    result = recover(tmp_path, queue, now=time.time() + 10)

    assert result["expired_leases"] == 1
    mission = queue.get("m-crash")
    assert mission.status is QueueStatus.PENDING
    assert mission.lease_owner is None

    again = queue.claim_next(owner="worker-b", lease_seconds=30)
    assert again is not None
    assert again.mission_id == "m-crash"
    assert again.attempts == 2


def test_exhausted_retries_are_blocked_with_reason(tmp_path) -> None:
    queue = PersistentMissionQueue(tmp_path / "q.db")
    queue.enqueue(
        mission_id="m-dead",
        objective="ölü görev",
        primary_department="oyun",
        max_attempts=1,
    )
    queue.claim_next(owner="worker-a", lease_seconds=1)
    mission = queue.get("m-dead")
    assert mission.attempts >= mission.max_attempts

    result = recover(tmp_path, queue, now=time.time() + 10)

    assert result["blocked"] == ["m-dead"]
    blocked = queue.get("m-dead")
    assert blocked.status is QueueStatus.BLOCKED
    assert "yarım kalan işlem" in (blocked.last_error or "")


def test_recovery_is_idempotent(tmp_path) -> None:
    queue = PersistentMissionQueue(tmp_path / "q.db")
    queue.enqueue(
        mission_id="m-once",
        objective="tek",
        primary_department="oyun",
        max_attempts=1,
    )
    queue.claim_next(owner="worker-a", lease_seconds=1)

    first = recover(tmp_path, queue, now=time.time() + 10)
    second = recover(tmp_path, queue, now=time.time() + 20)

    assert first["blocked"] == ["m-once"]
    assert second["blocked"] == []
    assert queue.get("m-once").status is QueueStatus.BLOCKED
