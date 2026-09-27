import json
import subprocess
import sys
from pathlib import Path

from ahos.autonomous_company import PersistentMissionQueue, QueueStatus
from ahos.control_center import ControlCenterState, render_coding_review, render_dashboard
from ahos.coding_supervisor import CodingSupervisor, CodingSupervisorStore, CodingTaskStatus
from ahos.coding_worker import AutonomousCodingWorker, CodingBacklogItem
from ahos.mission_orchestrator import MissionResult, MissionStatus, MissionStepSpec
from ahos.owner_approval import OwnerApprovalInbox
from ahos.studio_approval import _hash
from ahos.studio_executor import StudioExecutor


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
    assert "Studio Execution" in body
    assert "Coding Supervisor" in body
    assert "Create Coding Task" in body


def test_snapshot_exposes_persisted_studio_execution(tmp_path: Path):
    runtime = tmp_path / "runtime"
    studio = runtime / "episodes" / "S01E009"
    studio.mkdir(parents=True)
    decision = {
        "episode_id": "S01E009", "owner_approved": True,
        "paid_execution_enabled": True, "external_execution_enabled": True,
        "publishing_enabled": False, "max_budget_usd": 2.0,
    }
    decision["decision_hash"] = _hash(decision)
    (studio / "OWNER-DECISION.json").write_text(json.dumps(decision), encoding="utf-8")
    (studio / "EXECUTION-PREFLIGHT.json").write_text(json.dumps({
        "episode_id": "S01E009", "approval_ready": True,
        "cost_estimate": {"recommended_budget_ceiling": 1.0},
    }), encoding="utf-8")
    StudioExecutor(studio, {}).initialize()
    snapshot = ControlCenterState(runtime).snapshot()
    assert snapshot["studio_executions"][0]["episode_id"] == "S01E009"
    assert "Studio Execution" in render_dashboard(snapshot)


def test_snapshot_exposes_coding_queue_read_only_status(tmp_path: Path):
    state = ControlCenterState(tmp_path / "runtime")
    repository = tmp_path / "repo"
    repository.mkdir()
    CodingSupervisorStore(state.coding_queue_path).enqueue(
        CodingBacklogItem(
            task_id="CODE-9", title="queued change", repository=repository,
            allowed_paths=("src",),
        )
    )
    coding = state.snapshot()["coding_supervisor"]
    assert coding["counts"]["queued"] == 1
    assert coding["tasks"][0]["task_id"] == "CODE-9"


def _waiting_coding_task(state: ControlCenterState, tmp_path: Path):
    bare = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", "-q", str(bare)], check=True)
    repository = tmp_path / "repo"
    repository.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repository, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repository, check=True)
    (repository / "src").mkdir()
    (repository / "src" / "value.py").write_text("VALUE = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repository, check=True)
    subprocess.run(["git", "commit", "-qm", "initial"], cwd=repository, check=True)
    subprocess.run(["git", "remote", "add", "origin", str(bare)], cwd=repository, check=True)
    subprocess.run(["git", "push", "-qu", "origin", "HEAD:main"], cwd=repository, check=True)
    subprocess.run(["git", "branch", "--set-upstream-to=origin/main"], cwd=repository, check=True)

    store = CodingSupervisorStore(state.coding_queue_path)
    store.enqueue(CodingBacklogItem(
        task_id="CODE-PANEL", title="panel-approved edit", repository=repository,
        allowed_paths=("src",), test_commands=((sys.executable, "-c", "assert True"),),
    ))

    def builder(_prompt: str, worktree: Path):
        (worktree / "src" / "value.py").write_text("VALUE = 2\n", encoding="utf-8")

    result = CodingSupervisor(
        store=store,
        worker=AutonomousCodingWorker(runner=builder, workspace_root=tmp_path / "workers"),
        worker_id="dev-01",
        test_command_policy=lambda command: command[0] == sys.executable,
    ).run_once()
    assert result.status is CodingTaskStatus.WAITING_OWNER_APPROVAL
    return repository, bare, store


def test_dashboard_can_reject_coding_task_without_touching_repository(tmp_path: Path):
    state = ControlCenterState(tmp_path / "runtime")
    repository, _bare, store = _waiting_coding_task(state, tmp_path)
    before = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repository,
                            text=True, capture_output=True, check=True).stdout

    assert "coding task rejected" in state.decide_coding_task("CODE-PANEL", approved=False)
    assert store.get("CODE-PANEL").status is CodingTaskStatus.OWNER_REJECTED
    after = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repository,
                           text=True, capture_output=True, check=True).stdout
    assert after == before


def test_dashboard_approval_applies_tests_commits_and_pushes(tmp_path: Path):
    state = ControlCenterState(tmp_path / "runtime")
    repository, bare, store = _waiting_coding_task(state, tmp_path)

    message = state.decide_coding_task("CODE-PANEL", approved=True)

    assert "approved, tested, committed and pushed" in message
    assert store.get("CODE-PANEL").status is CodingTaskStatus.OWNER_APPROVED
    assert (repository / "src" / "value.py").read_text(encoding="utf-8") == "VALUE = 2\n"
    local = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repository,
                           text=True, capture_output=True, check=True).stdout.strip()
    remote = subprocess.run(["git", "--git-dir", str(bare), "rev-parse", "main"],
                            text=True, capture_output=True, check=True).stdout.strip()
    assert remote == local
    assert "Approve &amp; Publish" not in render_dashboard(state.snapshot())


def test_dashboard_approval_refuses_tracked_owner_changes(tmp_path: Path):
    state = ControlCenterState(tmp_path / "runtime")
    repository, _bare, store = _waiting_coding_task(state, tmp_path)
    (repository / "src" / "value.py").write_text("OWNER = True\n", encoding="utf-8")

    try:
        state.decide_coding_task("CODE-PANEL", approved=True)
    except ValueError as exc:
        assert "tracked changes" in str(exc)
    else:
        raise AssertionError("dirty repository was accepted")
    assert store.get("CODE-PANEL").status is CodingTaskStatus.WAITING_OWNER_APPROVAL


def test_dashboard_reconciles_patch_that_owner_already_integrated(tmp_path: Path):
    state = ControlCenterState(tmp_path / "runtime")
    repository, _bare, store = _waiting_coding_task(state, tmp_path)
    task = store.get("CODE-PANEL")
    subprocess.run(["git", "apply", task.patch_file], cwd=repository, check=True)
    subprocess.run(["git", "add", "src/value.py"], cwd=repository, check=True)
    subprocess.run(["git", "commit", "-qm", "owner integrated"], cwd=repository, check=True)

    message = state.decide_coding_task("CODE-PANEL", approved=True)

    assert "already integrated" in message
    assert store.get("CODE-PANEL").status is CodingTaskStatus.OWNER_APPROVED


def test_panel_creates_natural_language_coding_task_with_safe_scope(tmp_path: Path):
    repository = tmp_path / "repo"
    repository.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
    state = ControlCenterState(repository / "runtime")

    message = state.create_coding_task("Add a health indicator", "core")

    assert "coding task queued" in message
    task = CodingSupervisorStore(state.coding_queue_path).all()[0]
    assert task.title == "Add a health indicator"
    assert task.allowed_paths == (
        "ahos_core/ahos", "ahos_core/tests", "ahos_core/docs",
        "ahos_core/README.md", "ahos_core/pyproject.toml",
    )
    assert task.test_commands[0][1:] == ("-m", "pytest", "-q", "ahos_core/tests")


def test_code_review_renders_patch_evidence_and_actions(tmp_path: Path):
    state = ControlCenterState(tmp_path / "runtime")
    _repository, _bare, _store = _waiting_coding_task(state, tmp_path)

    review = state.coding_review("CODE-PANEL")
    body = render_coding_review(review)

    assert "VALUE = 2" in body
    assert "patch_sha256" in body
    assert "Approve &amp; Publish" in body
    assert "python" in body.lower()
