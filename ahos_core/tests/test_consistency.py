from __future__ import annotations

import sqlite3

from ahos.autonomous_company import PersistentMissionQueue, QueueStatus
from ahos.consistency import MissionQueueConsistencyChecker
from ahos.mission_orchestrator import MissionStepSpec
from ahos.owner_approval import OwnerApprovalInbox


def _protected_step():
    return MissionStepSpec(
        step_id="publish", title="publish", department="software",
        required_capabilities=frozenset({"build"}),
        external_side_effect=True,
    )


def test_consistency_reports_orphan_approval(tmp_path):
    queue = PersistentMissionQueue(tmp_path / "missions.db")
    inbox = OwnerApprovalInbox(tmp_path / "approvals.db")
    inbox.ensure_for_step("MISSING", _protected_step())
    codes = {d.code for d in MissionQueueConsistencyChecker(queue, inbox).check()}
    assert "orphan_approval" in codes


def test_consistency_reports_waiting_state_mismatch(tmp_path):
    queue = PersistentMissionQueue(tmp_path / "missions.db")
    inbox = OwnerApprovalInbox(tmp_path / "approvals.db")
    queue.enqueue(mission_id="M1", objective="x", primary_department="software")
    inbox.ensure_for_step("M1", _protected_step())
    codes = {d.code for d in MissionQueueConsistencyChecker(queue, inbox).check()}
    assert "waiting_approval_state_mismatch" in codes


def test_consistency_reports_waiting_mission_without_approval(tmp_path):
    queue = PersistentMissionQueue(tmp_path / "missions.db")
    inbox = OwnerApprovalInbox(tmp_path / "approvals.db")
    queue.enqueue(mission_id="M1", objective="x", primary_department="software")
    with sqlite3.connect(queue.path) as conn:
        conn.execute(
            "UPDATE missions SET status=? WHERE mission_id=?",
            (QueueStatus.WAITING_OWNER_APPROVAL.value, "M1"),
        )
    codes = {d.code for d in MissionQueueConsistencyChecker(queue, inbox).check()}
    assert "waiting_mission_without_approval" in codes


def test_consistency_reports_invalid_running_lease(tmp_path):
    queue = PersistentMissionQueue(tmp_path / "missions.db")
    inbox = OwnerApprovalInbox(tmp_path / "approvals.db")
    queue.enqueue(mission_id="M1", objective="x", primary_department="software")
    with sqlite3.connect(queue.path) as conn:
        conn.execute(
            "UPDATE missions SET status=?, lease_owner=NULL, lease_until=NULL WHERE mission_id=?",
            (QueueStatus.RUNNING.value, "M1"),
        )
    codes = {d.code for d in MissionQueueConsistencyChecker(queue, inbox).check()}
    assert "invalid_running_lease" in codes


def test_consistency_is_empty_for_simple_pending_mission(tmp_path):
    queue = PersistentMissionQueue(tmp_path / "missions.db")
    inbox = OwnerApprovalInbox(tmp_path / "approvals.db")
    queue.enqueue(mission_id="M1", objective="x", primary_department="software")
    assert MissionQueueConsistencyChecker(queue, inbox).check() == ()
