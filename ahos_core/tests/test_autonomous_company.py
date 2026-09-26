from __future__ import annotations

import json
from pathlib import Path

from ahos.autonomous_company import (
    CompanyLoop,
    PersistentMissionQueue,
    QueueStatus,
)
from ahos.mission_orchestrator import (
    MissionResult,
    MissionStatus,
)


def _result(
    *,
    mission_id: str,
    objective: str,
    status: MissionStatus,
    reason: str,
) -> MissionResult:
    return MissionResult(
        mission_id=mission_id,
        objective=objective,
        manager_id="mgr-software-01",
        status=status,
        steps=(),
        reason=reason,
    )


def test_queue_persists_across_instances(tmp_path: Path) -> None:
    db = tmp_path / "missions.db"

    queue1 = PersistentMissionQueue(db)
    queue1.enqueue(
        mission_id="m1",
        objective="build internal tool",
        primary_department="software",
    )

    queue2 = PersistentMissionQueue(db)
    mission = queue2.get("m1")

    assert mission is not None
    assert mission.status is QueueStatus.PENDING
    assert mission.objective == "build internal tool"


def test_claim_is_leased_and_not_claimed_twice(tmp_path: Path) -> None:
    queue = PersistentMissionQueue(tmp_path / "missions.db")
    queue.enqueue(
        mission_id="m1",
        objective="task",
        primary_department="software",
    )

    first = queue.claim_next(owner="worker-a", lease_seconds=60)
    second = queue.claim_next(owner="worker-b", lease_seconds=60)

    assert first is not None
    assert first.status is QueueStatus.RUNNING
    assert first.lease_owner == "worker-a"
    assert second is None


def test_company_loop_completes_multiple_missions_until_idle(
    tmp_path: Path,
) -> None:
    queue = PersistentMissionQueue(tmp_path / "missions.db")
    for mission_id in ("m1", "m2", "m3"):
        queue.enqueue(
            mission_id=mission_id,
            objective=f"objective {mission_id}",
            primary_department="software",
        )

    seen: list[str] = []

    def executor(mission):
        seen.append(mission.mission_id)
        return _result(
            mission_id=mission.mission_id,
            objective=mission.objective,
            status=MissionStatus.COMPLETED,
            reason="local deterministic mission completed",
        )

    processed = CompanyLoop(
        queue=queue,
        executor=executor,
        owner="loop-1",
    ).run_until_idle()

    assert seen == ["m1", "m2", "m3"]
    assert len(processed) == 3
    assert all(
        mission.status is QueueStatus.COMPLETED
        for mission in queue.list()
    )


def test_blocked_mission_does_not_auto_retry(tmp_path: Path) -> None:
    queue = PersistentMissionQueue(tmp_path / "missions.db")
    queue.enqueue(
        mission_id="m1",
        objective="requires owner approval",
        primary_department="software",
        max_attempts=3,
    )

    loop = CompanyLoop(
        queue=queue,
        executor=lambda mission: _result(
            mission_id=mission.mission_id,
            objective=mission.objective,
            status=MissionStatus.BLOCKED,
            reason="owner approval required",
        ),
        owner="loop-1",
    )
    loop.run_once()

    mission = queue.get("m1")
    assert mission is not None
    assert mission.status is QueueStatus.BLOCKED
    assert mission.attempts == 1
    assert "owner approval" in (mission.last_error or "")


def test_exception_retries_only_within_bound(tmp_path: Path) -> None:
    queue = PersistentMissionQueue(tmp_path / "missions.db")
    queue.enqueue(
        mission_id="m1",
        objective="retry me",
        primary_department="software",
        max_attempts=2,
    )

    def failing(_mission):
        raise RuntimeError("boom")

    loop = CompanyLoop(
        queue=queue,
        executor=failing,
        owner="loop-1",
        retry_delay_seconds=0,
    )

    first = loop.run_once()
    assert first is not None
    assert first.status is QueueStatus.PENDING
    assert first.attempts == 1

    second = loop.run_once()
    assert second is not None
    assert second.status is QueueStatus.FAILED
    assert second.attempts == 2

    third = loop.run_once()
    assert third is None


def test_expired_lease_is_recovered(tmp_path: Path) -> None:
    queue = PersistentMissionQueue(tmp_path / "missions.db")
    queue.enqueue(
        mission_id="m1",
        objective="recover me",
        primary_department="software",
    )

    claimed = queue.claim_next(
        owner="dead-loop",
        lease_seconds=1,
        now=100.0,
    )
    assert claimed is not None
    assert claimed.status is QueueStatus.RUNNING

    recovered = queue.recover_expired_leases(now=102.0)
    assert recovered == 1

    mission = queue.get("m1")
    assert mission is not None
    assert mission.status is QueueStatus.PENDING
    assert mission.lease_owner is None


def test_completion_persists_audit_result_json(tmp_path: Path) -> None:
    queue = PersistentMissionQueue(tmp_path / "missions.db")
    queue.enqueue(
        mission_id="m1",
        objective="audit mission",
        primary_department="software",
    )

    CompanyLoop(
        queue=queue,
        executor=lambda mission: _result(
            mission_id=mission.mission_id,
            objective=mission.objective,
            status=MissionStatus.COMPLETED,
            reason="done",
        ),
        owner="loop-1",
    ).run_once()

    mission = queue.get("m1")
    assert mission is not None
    assert mission.status is QueueStatus.COMPLETED
    assert mission.result_json is not None

    payload = json.loads(mission.result_json)
    assert payload["mission_id"] == "m1"
    assert payload["status"] == "completed"
    assert payload["reason"] == "done"
