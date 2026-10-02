from pathlib import Path

import pytest

from ahos.autonomous_company import CompanyLoop, PersistentMissionQueue, QueueStatus
from ahos.mission_orchestrator import (
    MissionResult,
    MissionStatus,
    MissionStepSpec,
    OwnerApprovalPending,
    OwnerApprovalRejected,
)
from ahos.owner_approval import (
    ApprovalAwareManagerPlanner,
    ApprovalStatus,
    OwnerApprovalInbox,
)


def protected_step():
    return MissionStepSpec(
        step_id="publish",
        title="Publish externally",
        department="software",
        required_capabilities=frozenset({"automation"}),
        external_side_effect=True,
        requires_owner_approval=True,
    )


def delegate(mission_id, objective, manager_id):
    return (protected_step(),)


def test_inbox_persists_waiting_request(tmp_path: Path):
    inbox = OwnerApprovalInbox(tmp_path / "approvals.db")
    req = inbox.ensure_for_step("m1", protected_step())
    assert req is not None
    assert req.status is ApprovalStatus.WAITING_OWNER_APPROVAL
    assert [r.request_id for r in inbox.list_waiting()] == ["m1:publish"]
    reopened = OwnerApprovalInbox(tmp_path / "approvals.db")
    assert reopened.get("m1:publish").status is ApprovalStatus.WAITING_OWNER_APPROVAL


def test_planner_fails_closed_until_owner_approves(tmp_path: Path):
    inbox = OwnerApprovalInbox(tmp_path / "approvals.db")
    planner = ApprovalAwareManagerPlanner(delegate, inbox)
    with pytest.raises(OwnerApprovalPending):
        tuple(planner("m1", "objective", "mgr-software-01"))
    inbox.approve("m1:publish")
    steps = tuple(planner("m1", "objective", "mgr-software-01"))
    assert steps[0].owner_approved is True


def test_rejected_request_blocks_execution(tmp_path: Path):
    inbox = OwnerApprovalInbox(tmp_path / "approvals.db")
    planner = ApprovalAwareManagerPlanner(delegate, inbox)
    with pytest.raises(OwnerApprovalPending):
        tuple(planner("m1", "objective", "mgr-software-01"))
    inbox.reject("m1:publish")
    with pytest.raises(OwnerApprovalRejected):
        tuple(planner("m1", "objective", "mgr-software-01"))


def test_company_loop_persists_waiting_owner_approval(tmp_path: Path):
    queue = PersistentMissionQueue(tmp_path / "missions.db")
    queue.enqueue(
        mission_id="m1",
        objective="protected mission",
        primary_department="software",
        max_attempts=1,
    )

    def waiting_executor(mission):
        return MissionResult(
            mission_id=mission.mission_id,
            objective=mission.objective,
            manager_id="mgr-software-01",
            status=MissionStatus.WAITING_OWNER_APPROVAL,
            steps=(),
            reason="waiting for owner approval",
        )

    result = CompanyLoop(queue=queue, executor=waiting_executor).run_once()
    assert result is not None
    assert result.status is QueueStatus.WAITING_OWNER_APPROVAL
    assert queue.claim_next(owner="other") is None


def test_waiting_mission_can_be_requeued_after_approval(tmp_path: Path):
    queue = PersistentMissionQueue(tmp_path / "missions.db")
    queue.enqueue(
        mission_id="m1",
        objective="protected mission",
        primary_department="software",
        max_attempts=1,
    )
    claimed = queue.claim_next(owner="worker")
    assert claimed is not None
    result = MissionResult(
        mission_id="m1",
        objective="protected mission",
        manager_id="mgr-software-01",
        status=MissionStatus.WAITING_OWNER_APPROVAL,
        steps=(),
        reason="waiting",
    )
    queue.wait_for_owner_approval("m1", owner="worker", result=result)
    resumed = queue.resume_after_owner_approval("m1")
    assert resumed.status is QueueStatus.PENDING
    assert resumed.attempts == 0
    claimed_again = queue.claim_next(owner="worker-2")
    assert claimed_again is not None
    assert claimed_again.status is QueueStatus.RUNNING
