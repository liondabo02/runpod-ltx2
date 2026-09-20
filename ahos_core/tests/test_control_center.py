from pathlib import Path

from ahos.autonomous_company import PersistentMissionQueue, QueueStatus
from ahos.control_center import ControlCenterState, render_dashboard
from ahos.mission_orchestrator import MissionResult, MissionStatus, MissionStepSpec
from ahos.owner_approval import OwnerApprovalInbox


def make_waiting(queue: PersistentMissionQueue, mission_id: str = "m1"):
    queue.enqueue(
        mission_id=mission_id,
        objective="protected mission",
        primary_department="software",
        max_attempts=1,
    )
    queue.claim_next(owner="worker")
    queue.wait_for_owner_approval(
        mission_id,
        owner="worker",
        result=MissionResult(
            mission_id=mission_id,
            objective="protected mission",
            manager_id="mgr-software-01",
            status=MissionStatus.WAITING_OWNER_APPROVAL,
            steps=(),
            reason="waiting",
        ),
    )


def make_approval(inbox: OwnerApprovalInbox, mission_id: str = "m1"):
    return inbox.ensure_for_step(
        mission_id,
        MissionStepSpec(
            step_id="publish",
            title="Publish externally",
            department="software",
            required_capabilities=frozenset({"automation"}),
            external_side_effect=True,
            requires_owner_approval=True,
        ),
    )


def test_snapshot_shows_workers_and_queue(tmp_path: Path):
    state = ControlCenterState(tmp_path / "runtime")
    queue = PersistentMissionQueue(state.queue_db)
    queue.enqueue(
        mission_id="m1",
        objective="local mission",
        primary_department="software",
    )
    snap = state.snapshot()
    assert snap["mission_counts"]["pending"] == 1
    assert snap["worker_count"] >= 22


def test_approve_resumes_waiting_mission(tmp_path: Path):
    state = ControlCenterState(tmp_path / "runtime")
    queue = PersistentMissionQueue(state.queue_db)
    make_waiting(queue)
    req = make_approval(OwnerApprovalInbox(state.approvals_db))
    assert req is not None
    assert "mission resumed" in state.approve(req.request_id)
    assert queue.get("m1").status is QueueStatus.PENDING


def test_reject_blocks_waiting_mission(tmp_path: Path):
    state = ControlCenterState(tmp_path / "runtime")
    queue = PersistentMissionQueue(state.queue_db)
    make_waiting(queue)
    req = make_approval(OwnerApprovalInbox(state.approvals_db))
    assert req is not None
    assert "mission blocked" in state.reject(req.request_id)
    assert queue.get("m1").status is QueueStatus.BLOCKED


def test_kill_switch_and_backup(tmp_path: Path):
    state = ControlCenterState(tmp_path / "runtime")
    PersistentMissionQueue(state.queue_db)
    state.activate_kill_switch()
    assert state.stop_path.exists()
    assert "backup created" in state.create_backup()
    backups = list(state.backup_root.iterdir())
    assert len(backups) == 1
    assert (backups[0] / "manifest.json").exists()


def test_dashboard_html_contains_control_surfaces(tmp_path: Path):
    body = render_dashboard(ControlCenterState(tmp_path / "runtime").snapshot())
    assert "AHOS Holding Control Center" in body
    assert "Approval Inbox" in body
    assert "Mission Queue" in body
    assert "Virtual Workforce" in body
    assert "KILL SWITCH" in body
