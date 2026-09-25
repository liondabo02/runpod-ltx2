from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest

from ahos.coding_supervisor import CodingSupervisor, CodingSupervisorStore, CodingTaskStatus
from ahos.coding_worker import AutonomousCodingWorker, CodingBacklogItem


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "initial"], cwd=repo, check=True)
    return repo


def _item(repo: Path, task_id: str = "CODE-1") -> CodingBacklogItem:
    return CodingBacklogItem(
        task_id=task_id, title="safe edit", repository=repo,
        allowed_paths=("src",),
        test_commands=((sys.executable, "-c", "assert True"),),
    )


def _allow_python(command) -> bool:
    return tuple(command[:1]) == (sys.executable,)


def test_supervisor_persists_idempotent_task_and_stops_at_owner_gate(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    store = CodingSupervisorStore(tmp_path / "queue.json")
    item = _item(repo)
    first = store.enqueue(item, idempotency_key="issue:7", max_attempts=2)
    assert store.enqueue(item, idempotency_key="issue:7", max_attempts=2) == first

    def builder(_prompt: str, worktree: Path):
        (worktree / "src" / "app.py").write_text("VALUE = 2\n", encoding="utf-8")

    supervisor = CodingSupervisor(
        store=store,
        worker=AutonomousCodingWorker(runner=builder, workspace_root=tmp_path / "workers"),
        worker_id="supervisor-1", test_command_policy=_allow_python,
    )
    result = supervisor.run_once()
    assert result and result.status is CodingTaskStatus.WAITING_OWNER_APPROVAL
    assert result.attempts == 1
    assert subprocess.run(["git", "status", "--porcelain"], cwd=repo,
                          capture_output=True, text=True, check=True).stdout == ""
    approved = store.record_owner_decision(item.task_id, approved=True)
    assert approved.status is CodingTaskStatus.OWNER_APPROVED
    assert subprocess.run(["git", "log", "-1", "--format=%s"], cwd=repo,
                          capture_output=True, text=True, check=True).stdout.strip() == "initial"


def test_idempotency_key_rejects_different_payload(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    store = CodingSupervisorStore(tmp_path / "queue.json")
    store.enqueue(_item(repo), idempotency_key="same")
    with pytest.raises(ValueError, match="different task payload"):
        store.enqueue(_item(repo, "CODE-2"), idempotency_key="same")


def test_bounded_retries_and_policy_is_fail_closed(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    store = CodingSupervisorStore(tmp_path / "queue.json")
    store.enqueue(_item(repo), max_attempts=2)
    worker = AutonomousCodingWorker(runner=lambda *_: None, workspace_root=tmp_path / "workers")
    supervisor = CodingSupervisor(store=store, worker=worker, worker_id="s")
    assert supervisor.run_once().status is CodingTaskStatus.QUEUED
    assert supervisor.run_once().status is CodingTaskStatus.RETRIES_EXHAUSTED
    assert store.get("CODE-1").attempts == 2


def test_owner_decision_rejects_modified_patch(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    store = CodingSupervisorStore(tmp_path / "queue.json")
    store.enqueue(_item(repo))

    def builder(_prompt: str, worktree: Path):
        (worktree / "src" / "app.py").write_text("VALUE = 2\n", encoding="utf-8")

    result = CodingSupervisor(
        store=store,
        worker=AutonomousCodingWorker(runner=builder, workspace_root=tmp_path / "workers"),
        worker_id="s", test_command_policy=_allow_python,
    ).run_once()
    Path(result.patch_file).write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="patch was modified"):
        store.record_owner_decision("CODE-1", approved=True)


def test_worker_rechecks_scope_after_tests(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / "protected.txt").write_text("safe\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "protected"], cwd=repo, check=True)
    item = CodingBacklogItem(
        task_id="MUTATE", title="test mutation", repository=repo,
        allowed_paths=("src",),
        test_commands=((sys.executable, "-c", "from pathlib import Path; Path('protected.txt').write_text('bad')"),),
    )

    def builder(_prompt: str, worktree: Path):
        (worktree / "src" / "app.py").write_text("VALUE = 2\n", encoding="utf-8")

    result = AutonomousCodingWorker(runner=builder, workspace_root=tmp_path / "workers").run(item, "s")
    assert result.status.value == "blocked"
    assert "tests changed files outside approved scope" in result.reason


def test_store_recovers_abandoned_stale_lock(tmp_path: Path) -> None:
    store = CodingSupervisorStore(tmp_path / "queue.json", lock_timeout_seconds=0.2,
                                  stale_lock_seconds=0.01)
    store.lock_path.write_text("dead-process\n", encoding="ascii")
    time.sleep(0.02)
    assert store.status()["counts"]["queued"] == 0
    assert not store.lock_path.exists()
