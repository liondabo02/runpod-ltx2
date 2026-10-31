"""Queue must reject contradictory completion claims before changing SQLite state."""

from __future__ import annotations

import pytest

from ahos.autonomous_company import PersistentMissionQueue, QueueStatus
from ahos.mission_orchestrator import (
    MissionResult, MissionStatus, MissionStepResult, MissionStepSpec,
)
from ahos.workforce_execution import WorkStage


def _result(*, ident="mission-1", status=MissionStatus.COMPLETED, steps=()):
    return MissionResult(
        mission_id=ident, objective="one isolated task",
        manager_id="manager", status=status, steps=steps, reason="test",
    )


def _running(tmp_path):
    queue = PersistentMissionQueue(tmp_path / "queue.db")
    queue.enqueue(mission_id="mission-1", objective="one isolated task",
                  primary_department="software")
    claimed = queue.claim_next(owner="worker-1")
    assert claimed is not None
    assert claimed.status is QueueStatus.RUNNING
    return queue


def test_blocked_result_cannot_be_saved_as_completed(tmp_path):
    queue = _running(tmp_path)
    with pytest.raises(ValueError, match="only completed"):
        queue.complete("mission-1", owner="worker-1", result=_result(status=MissionStatus.BLOCKED))
    assert queue.get("mission-1").status is QueueStatus.RUNNING


def test_different_mission_identity_is_rejected_before_db_write(tmp_path):
    queue = _running(tmp_path)
    with pytest.raises(ValueError, match="different mission"):
        queue.complete("mission-1", owner="worker-1", result=_result(ident="mission-2"))
    assert queue.get("mission-1").status is QueueStatus.RUNNING


def test_uncompleted_step_prevents_completion(tmp_path):
    queue = _running(tmp_path)
    spec = MissionStepSpec(
        step_id="build", title="Make file", department="software",
        required_capabilities=frozenset({"python"}),
    )
    step = MissionStepResult(
        step=spec, stage=WorkStage.BLOCKED, worker_id="worker-1",
        worker_summary="blocked", qa_summary="not passed", reason="failed",
    )
    with pytest.raises(ValueError, match="step"):
        queue.complete("mission-1", owner="worker-1", result=_result(steps=(step,)))
    assert queue.get("mission-1").status is QueueStatus.RUNNING


def test_valid_result_saves_matching_status(tmp_path):
    queue = _running(tmp_path)
    queue.complete("mission-1", owner="worker-1", result=_result())
    row = queue.get("mission-1")
    assert row.status is QueueStatus.COMPLETED
    assert '"status": "completed"' in row.result_json
