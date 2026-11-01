from __future__ import annotations

import json
from pathlib import Path

from ahos.autonomous_company import PersistentMissionQueue, QueueStatus
from ahos.mission_orchestrator import MissionResult, MissionStatus
from ahos.queue_repair import reopen_blocked


def _block(queue: PersistentMissionQueue, mission_id: str, error: str) -> None:
    queue.enqueue(
        mission_id=mission_id,
        objective="engelli iş",
        primary_department="oyun",
        max_attempts=1,
    )
    queue.claim_next(owner="worker-x", lease_seconds=1)
    queue.block(
        mission_id,
        owner="worker-x",
        result=MissionResult(
            mission_id=mission_id,
            objective="engelli iş",
            manager_id=None,
            status=MissionStatus.BLOCKED,
            steps=(),
            reason=error,
        ),
    )


def test_lock_blocked_mission_is_reopened_with_fresh_id(tmp_path) -> None:
    queue = PersistentMissionQueue(tmp_path / "company-service.db")
    _block(queue, "CMD-oyun-a-1", "görev başka işçide veya kapalı: CMD-oyun-a-1")

    report = reopen_blocked(tmp_path)

    assert report["candidates"] == 1
    new_id = report["planned"][0]["new"]
    assert new_id == "CMD-oyun-a-1-r2"
    fresh = queue.get(new_id)
    assert fresh is not None and fresh.status is QueueStatus.PENDING
    # tarih korunur: eski satır silinmez
    assert queue.get("CMD-oyun-a-1").status is QueueStatus.BLOCKED


def test_stale_work_item_is_moved_aside(tmp_path) -> None:
    queue = PersistentMissionQueue(tmp_path / "company-service.db")
    _block(queue, "CMD-oyun-b-2", "sahiplenilemedi: kilit")
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    (tasks / "CMD-oyun-b-2.json").write_text(json.dumps({"step": "produce"}), encoding="utf-8")

    report = reopen_blocked(tmp_path)

    assert report["moved_items"] == ["CMD-oyun-b-2.json"]
    assert not (tasks / "CMD-oyun-b-2.json").exists()
    assert (tasks / "_stale" / "CMD-oyun-b-2.json").exists()


def test_dry_run_changes_nothing(tmp_path) -> None:
    queue = PersistentMissionQueue(tmp_path / "company-service.db")
    _block(queue, "CMD-oyun-c-3", "lease süresi geçti")

    report = reopen_blocked(tmp_path, dry_run=True)

    assert report["candidates"] == 1
    assert queue.get("CMD-oyun-c-3-r2") is None


def test_non_lock_blocks_are_untouched(tmp_path) -> None:
    queue = PersistentMissionQueue(tmp_path / "company-service.db")
    _block(queue, "CMD-oyun-d-4", "mission blocked at step produce: worker execution failed")

    report = reopen_blocked(tmp_path)

    assert report["candidates"] == 0


def test_second_reopen_uses_next_suffix(tmp_path) -> None:
    queue = PersistentMissionQueue(tmp_path / "company-service.db")
    _block(queue, "CMD-oyun-e-5", "kuyruk kilidi")

    first = reopen_blocked(tmp_path)
    assert first["planned"][0]["new"].endswith("-r2")

    queue.claim_next(owner="w", lease_seconds=1)
    queue.block(
        "CMD-oyun-e-5-r2",
        owner="w",
        result=MissionResult(
            mission_id="CMD-oyun-e-5-r2",
            objective="engelli iş",
            manager_id=None,
            status=MissionStatus.BLOCKED,
            steps=(),
            reason="kuyruk kilidi",
        ),
    )
    second = reopen_blocked(tmp_path)
    assert second["planned"][0]["new"] == "CMD-oyun-e-5-r3"
