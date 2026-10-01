from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from ahos.coding_worker import (
    AutonomousCodingWorker,
    CodingBacklogItem,
    CodingWorkerStatus,
    GitCommandError,
)


def test_core_test_process_receives_only_candidate_package_on_pythonpath(
    tmp_path: Path, monkeypatch
) -> None:
    repo = _repository(tmp_path)
    (repo / "ahos_core").mkdir()
    (repo / "ahos_core" / "marker_module.py").write_text("VALUE = 7\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "add core"], cwd=repo, check=True)
    item = CodingBacklogItem(
        task_id="PYTHONPATH-1",
        title="test core import",
        repository=repo,
        allowed_paths=("src", "ahos_core"),
        test_commands=((
            sys.executable,
            "-c",
            (
                "import os; from pathlib import Path; import marker_module; "
                "assert marker_module.VALUE == 7; "
                "assert os.environ['PYTHONPATH'] == str(Path.cwd() / 'ahos_core'); "
                "assert os.environ['PYTHONNOUSERSITE'] == '1'"
            ),
        ),),
    )
    monkeypatch.setenv("PYTHONPATH", str(tmp_path / "owner-checkout"))

    def builder(_prompt: str, worktree: Path):
        (worktree / "src" / "app.py").write_text("VALUE = 2\n", encoding="utf-8")

    result = AutonomousCodingWorker(runner=builder, workspace_root=tmp_path / "workers").run(item, "worker")
    assert result.status is CodingWorkerStatus.WAITING_OWNER_APPROVAL


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


def test_worker_rechecks_scope_after_tests_mutate_worktree(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    item = CodingBacklogItem(
        task_id="BACKLOG-TEST-ESCAPE",
        title="Test command must remain in scope",
        repository=repository,
        allowed_paths=("src",),
        test_commands=(
            (
                sys.executable,
                "-c",
                "from pathlib import Path; Path('protected.txt').write_text('changed by test\\n')",
            ),
        ),
    )

    def builder(_prompt: str, worktree: Path):
        (worktree / "src" / "feature.py").write_text("VALUE = 2\n", encoding="utf-8")

    result = AutonomousCodingWorker(
        runner=builder, workspace_root=tmp_path / "workers"
    ).run(item, "dev-01")

    assert result.status is CodingWorkerStatus.BLOCKED
    assert "tests changed files outside approved scope" in result.reason
    assert result.changed_files == ("protected.txt", "src/feature.py")
    assert result.patch_file is None
    assert result.approval_file is None


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


def test_worker_blocks_accidental_removal_of_existing_public_api(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    (repository / "src" / "feature.py").write_text(
        "class ControlCenterState:\n    pass\n\ndef render_dashboard():\n    return 'ok'\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "."], cwd=repository, check=True)
    subprocess.run(["git", "commit", "-qm", "public api"], cwd=repository, check=True)

    def builder(_prompt: str, worktree: Path):
        (worktree / "src" / "feature.py").write_text(
            "def render_health():\n    return 'healthy'\n", encoding="utf-8"
        )

    result = AutonomousCodingWorker(
        runner=builder, workspace_root=tmp_path / "workers"
    ).run(_item(repository), "dev-01")

    assert result.status is CodingWorkerStatus.BLOCKED
    assert "compatibility gate rejected removal" in result.reason
    assert "ControlCenterState" in result.reason
    assert "render_dashboard" in result.reason


def test_worker_allows_broad_additive_architecture_and_compatibility_reexports(
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path)
    (repository / "src" / "feature.py").write_text(
        "class ControlCenterState:\n    pass\n", encoding="utf-8"
    )
    subprocess.run(["git", "add", "."], cwd=repository, check=True)
    subprocess.run(["git", "commit", "-qm", "public api"], cwd=repository, check=True)
    item = CodingBacklogItem(
        task_id="BROAD-ADDITIVE",
        title="Build a complete health subsystem",
        repository=repository,
        allowed_paths=("src",),
        test_commands=((sys.executable, "-c", "assert True"),),
    )

    def builder(prompt: str, worktree: Path):
        assert "complete scoped item" in prompt
        assert "add modules, classes, tests" in prompt
        (worktree / "src" / "health.py").write_text(
            "class HealthService:\n    pass\n", encoding="utf-8"
        )
        (worktree / "src" / "feature.py").write_text(
            "from health import HealthService\n\nclass ControlCenterState:\n    pass\n",
            encoding="utf-8",
        )

    result = AutonomousCodingWorker(
        runner=builder, workspace_root=tmp_path / "workers"
    ).run(item, "dev-01")

    assert result.status is CodingWorkerStatus.WAITING_OWNER_APPROVAL
    assert result.changed_files == ("src/feature.py", "src/health.py")


def test_worker_falls_back_to_scoped_checkout_when_full_checkout_fails(tmp_path: Path) -> None:
    repository = _repository(tmp_path)

    class FullCheckoutFailsOnce(AutonomousCodingWorker):
        failed = False

        def _git(self, repository: Path, *args: str) -> str:
            if args[:3] == ("worktree", "add", "--detach") and not self.failed:
                self.failed = True
                raise GitCommandError(args, 128, "unable to stat quarantined file")
            return super()._git(repository, *args)

    def builder(_prompt: str, worktree: Path):
        (worktree / "src" / "feature.py").write_text("VALUE = 2\n", encoding="utf-8")

    result = FullCheckoutFailsOnce(
        runner=builder, workspace_root=tmp_path / "workers"
    ).run(_item(repository), "dev-01")

    assert result.status is CodingWorkerStatus.WAITING_OWNER_APPROVAL
    assert result.changed_files == ("src/feature.py",)


def test_worker_uses_scoped_checkout_first_on_guarded_platform(tmp_path: Path) -> None:
    repository = _repository(tmp_path)

    class GuardedPlatformWorker(AutonomousCodingWorker):
        @staticmethod
        def _prefer_scoped_checkout() -> bool:
            return True

        def _git(self, repository: Path, *args: str) -> str:
            if args[:3] == ("worktree", "add", "--detach"):
                raise AssertionError("full checkout must not run")
            return super()._git(repository, *args)

    def builder(_prompt: str, worktree: Path):
        (worktree / "src" / "feature.py").write_text("VALUE = 2\n", encoding="utf-8")

    result = GuardedPlatformWorker(
        runner=builder, workspace_root=tmp_path / "workers"
    ).run(_item(repository), "dev-01")

    assert result.status is CodingWorkerStatus.WAITING_OWNER_APPROVAL


def test_guarded_checkout_excludes_unapproved_administrative_scripts(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repository, check=True)
    subprocess.run(["git", "config", "user.name", "AHOS Test"], cwd=repository, check=True)
    (repository / "ahos_core" / "ahos").mkdir(parents=True)
    (repository / "ahos_core" / "tests").mkdir()
    (repository / "ahos_core" / "scripts").mkdir()
    (repository / "ahos_core" / "ahos" / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    (repository / "ahos_core" / "tests" / "test_app.py").write_text("# test\n", encoding="utf-8")
    (repository / "ahos_core" / "scripts" / "Install.ps1").write_text("admin\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repository, check=True)
    subprocess.run(["git", "commit", "-qm", "initial"], cwd=repository, check=True)
    item = CodingBacklogItem(
        task_id="SCOPED-CORE", title="safe core edit", repository=repository,
        allowed_paths=("ahos_core/ahos", "ahos_core/tests"),
    )

    class GuardedPlatformWorker(AutonomousCodingWorker):
        @staticmethod
        def _prefer_scoped_checkout() -> bool:
            return True

    def builder(_prompt: str, worktree: Path):
        assert not (worktree / "ahos_core" / "scripts" / "Install.ps1").exists()
        (worktree / "ahos_core" / "ahos" / "app.py").write_text("VALUE = 2\n", encoding="utf-8")

    result = GuardedPlatformWorker(
        runner=builder, workspace_root=tmp_path / "workers",
    ).run(item, "dev-01")

    assert result.status is CodingWorkerStatus.WAITING_OWNER_APPROVAL


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
