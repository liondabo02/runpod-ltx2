from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

from ahos.coding_worker import AutonomousCodingWorker, CodingBacklogItem, CodingWorkerStatus


@dataclass(frozen=True, slots=True)
class WorkerExecutionE2EReport:
    changed_expected_file: bool
    real_test_passed: bool
    patch_evidence_present: bool
    owner_gate_stopped_publish: bool
    owner_repo_clean: bool
    passed: bool


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    return result.stdout.strip()


def run_worker_execution_e2e() -> WorkerExecutionE2EReport:
    """Real worker-engine run in an isolated temporary Git repository.

    The builder is deterministic/local so this proves worker execution,
    scoping, testing and approval evidence without claiming model-provider
    quality or consuming API budget.
    """
    with TemporaryDirectory(prefix="ahos-q99-worker-e2e-") as tmp:
        root = Path(tmp)
        repo = root / "repo"
        repo.mkdir()
        _git(repo, "init", "-q")
        _git(repo, "config", "user.email", "q99@example.invalid")
        _git(repo, "config", "user.name", "AHOS Q99")
        (repo / "src").mkdir()
        (repo / "src" / "feature.py").write_text("VALUE = 1\n", encoding="utf-8")
        _git(repo, "add", ".")
        _git(repo, "commit", "-qm", "initial")

        item = CodingBacklogItem(
            task_id="Q99-WORKER-E2E",
            title="Perform a real isolated scoped edit and verify it",
            repository=repo,
            allowed_paths=("src",),
            test_commands=((
                sys.executable,
                "-c",
                "from pathlib import Path; assert Path('src/feature.py').read_text().strip() == 'VALUE = 2'",
            ),),
        )

        def deterministic_builder(prompt: str, worktree: Path) -> None:
            if "Do not commit, push, merge" not in prompt:
                raise AssertionError("owner boundary missing from worker prompt")
            (worktree / "src" / "feature.py").write_text("VALUE = 2\n", encoding="utf-8")

        result = AutonomousCodingWorker(
            runner=deterministic_builder,
            workspace_root=root / "worker-attempts",
        ).run(item, "q99-worker")

        changed = result.changed_files == ("src/feature.py",)
        tested = bool(result.tests_run) and all(code == 0 for _, code in result.tests_run)
        patch_ok = bool(
            result.patch_file
            and result.patch_file.is_file()
            and b"VALUE = 2" in result.patch_file.read_bytes()
        )
        owner_gate = (
            result.status is CodingWorkerStatus.WAITING_OWNER_APPROVAL
            and result.approval_file is not None
            and result.approval_file.is_file()
        )
        if owner_gate:
            approval = json.loads(result.approval_file.read_text(encoding="utf-8"))
            owner_gate = (
                approval.get("push_enabled") is False
                and approval.get("merge_enabled") is False
                and len(str(approval.get("patch_sha256") or "")) == 64
            )
        owner_clean = _git(repo, "status", "--porcelain") == ""
        return WorkerExecutionE2EReport(
            changed_expected_file=changed,
            real_test_passed=tested,
            patch_evidence_present=patch_ok,
            owner_gate_stopped_publish=owner_gate,
            owner_repo_clean=owner_clean,
            passed=changed and tested and patch_ok and owner_gate and owner_clean,
        )
