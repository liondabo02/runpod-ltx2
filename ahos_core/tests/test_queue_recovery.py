"""Crash recovery and durable ownership tests for the mission queue."""

from __future__ import annotations

import time

from ahos.autonomous_company import PersistentMissionQueue
from ahos.queue_recovery import recover


def _queue(tmp_path) -> PersistentMissionQueue:
    return PersistentMissionQueue(tmp_path / "company-service.db")


def _enqueue(queue, mission_id: str) -> None:
    queue.enqueue(
        mission_id=mission_id,
        objective=f"görev {mission_id}",
        primary_department="oyun",
        max_attempts=1,
    )


def _force(queue, mission_id: str, sql: str, params: tuple) -> None:
    with queue._connect() as conn:  # noqa: SLF001 - test setup
        conn.execute(sql, params)


def test_expired_lease_is_returned_to_pending(tmp_path) -> None:
    queue = _queue(tmp_path)
    _enqueue(queue, "m1")
    _force(
        queue,
        "m1",
        "UPDATE missions SET status='running', lease_owner='worker', lease_until=? WHERE mission_id=?",
        (time.time() - 60, "m1"),
    )

    report = recover(queue)

    assert report["expired_leases"] == 1
    row = queue.get("m1")
    assert row.status.value == "pending"
    assert row.lease_owner in (None, "")


def test_stuck_pending_mission_is_reopened(tmp_path) -> None:
    queue = _queue(tmp_path)
    _enqueue(queue, "m2")
    _force(
        queue,
        "m2",
        "UPDATE missions SET attempts=1, max_attempts=1, next_attempt_at=0 WHERE mission_id=?",
        ("m2",),
    )

    report = recover(queue)

    assert report["reopened_stuck"] == 1
    row = queue.get("m2")
    assert row.attempts == 0, "yeniden denenebilmeli"
    assert row.max_attempts == 2


def test_mission_beyond_the_attempt_cap_is_blocked_not_looped(tmp_path) -> None:
    queue = _queue(tmp_path)
    _enqueue(queue, "m3")
    _force(
        queue,
        "m3",
        "UPDATE missions SET attempts=5, max_attempts=5, next_attempt_at=0 WHERE mission_id=?",
        ("m3",),
    )

    report = recover(queue, attempts_cap=3)

    assert report["gave_up"] == 1
    assert queue.get("m3").status.value == "blocked"


def test_recovery_is_idempotent_and_leaves_healthy_rows_alone(tmp_path) -> None:
    queue = _queue(tmp_path)
    _enqueue(queue, "healthy")
    _enqueue(queue, "broken")
    _force(
        queue,
        "broken",
        "UPDATE missions SET attempts=1, max_attempts=1, next_attempt_at=0 WHERE mission_id=?",
        ("broken",),
    )

    first = recover(queue)
    second = recover(queue)

    assert first["reopened_stuck"] == 1
    assert second["reopened_stuck"] == 0
    assert queue.get("healthy").status.value == "pending"
