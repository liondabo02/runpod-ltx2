from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from ahos.coding_worker import (
    AutonomousCodingWorker,
    CodingBacklogItem,
    CodingWorkerStatus,
)


def _repository(tmp_path: Path) -> Path:
    repository = tmp_path / "repo"
    repository.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repository, check=True)
    subprocess.run(["git", "config", "user.name", "AHOS Test"], cwd=repository, check=True)
    (repository / "src").mkdir()
    (repository / "src" / "feature.py").write_text("VALUE = 1\n", encoding="utf-8")
    (repository / "protected.txt").write_text("owner\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repository, check=True)
    subprocess.run(["git", "commit", "-qm", "initial"], cwd=repository, check=True)
    return repository


def _item(repository: Path) -> CodingBacklogItem:
    return CodingBacklogItem(
        task_id="BACKLOG-42",
        title="Implement scoped feature",
        repository=repository,
        allowed_paths=("src",),
        test_commands=((sys.executable, "-c", "from pathlib import Path; assert '2' in Path('src/feature.py').read_text()"),),
    )


def test_worker_builds_tests_and_stops_for_owner_approval(tmp_path: Path) -> None:
    repository = _repository(tmp_path)

    def builder(prompt: str, worktree: Path):
        assert "Do not commit, push, merge" in prompt
        (worktree / "src" / "feature.py").write_text("VALUE = 2\n", encoding="utf-8")

    result = AutonomousCodingWorker(
        runner=builder, workspace_root=tmp_path / "workers"
    ).run(_item(repository), "dev-01")

    assert result.status is CodingWorkerStatus.WAITING_OWNER_APPROVAL
    assert result.changed_files == ("src/feature.py",)
    assert result.patch_file and b"VALUE = 2" in result.patch_file.read_bytes()
    approval = json.loads(result.approval_file.read_text(encoding="utf-8"))
    assert approval["push_enabled"] is False
    assert approval["merge_enabled"] is False
    assert len(approval["patch_sha256"]) == 64
    assert subprocess.run(
        ["git", "status", "--porcelain"], cwd=repository, capture_output=True, text=True, check=True
    ).stdout == ""


def test_worker_blocks_changes_outside_scope(tmp_path: Path) -> None:
    repository = _repository(tmp_path)

    def builder(_prompt: str, worktree: Path):
        (worktree / "src" / "feature.py").write_text("VALUE = 2\n", encoding="utf-8")
        (worktree / "protected.txt").write_text("changed\n", encoding="utf-8")

    result = AutonomousCodingWorker(
        runner=builder, workspace_root=tmp_path / "workers"
    ).run(_item(repository), "dev-01")

    assert result.status is CodingWorkerStatus.BLOCKED
    assert "escaped approved scope" in result.reason
    assert result.patch_file is None


def test_worker_blocks_failed_tests_without_patch(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    item = CodingBacklogItem(
        task_id="BACKLOG-FAIL",
        title="Broken change",
        repository=repository,
        allowed_paths=("src",),
        test_commands=((sys.executable, "-c", "raise SystemExit(7)"),),
    )

    def builder(_prompt: str, worktree: Path):
        (worktree / "src" / "feature.py").write_text("VALUE = 2\n", encoding="utf-8")

    result = AutonomousCodingWorker(
        runner=builder, workspace_root=tmp_path / "workers"
    ).run(item, "dev-01")

    assert result.status is CodingWorkerStatus.BLOCKED
    assert "test failed (7)" in result.reason
    assert result.patch_file is None


def test_worker_patch_contains_new_files(tmp_path: Path) -> None:
    repository = _repository(tmp_path)

    def builder(_prompt: str, worktree: Path):
        (worktree / "src" / "feature.py").write_text("VALUE = 2\n", encoding="utf-8")
        (worktree / "src" / "new_module.py").write_text("ENABLED = True\n", encoding="utf-8")

    result = AutonomousCodingWorker(
        runner=builder, workspace_root=tmp_path / "workers"
    ).run(_item(repository), "dev-01")

    assert result.status is CodingWorkerStatus.WAITING_OWNER_APPROVAL
    assert result.patch_file and b"ENABLED = True" in result.patch_file.read_bytes()


def test_backlog_scope_rejects_parent_traversal(tmp_path: Path) -> None:
    try:
        CodingBacklogItem(
            task_id="unsafe",
            title="unsafe",
            repository=tmp_path,
            allowed_paths=("../outside",),
        )
    except ValueError as exc:
        assert "unsafe allowed path" in str(exc)
    else:
        raise AssertionError("unsafe scope accepted")
