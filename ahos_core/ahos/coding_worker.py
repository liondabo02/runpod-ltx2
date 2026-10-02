from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Sequence


BuilderRunner = Callable[[str, Path], Any]


class CodingWorkerStatus(str, Enum):
    BLOCKED = "blocked"
    WAITING_OWNER_APPROVAL = "waiting_owner_approval"


class GitCommandError(RuntimeError):
    """Git failure with the diagnostic output preserved for operators."""

    def __init__(self, args: Sequence[str], returncode: int, detail: str) -> None:
        self.args_argv = tuple(args)
        self.returncode = returncode
        self.detail = detail
        super().__init__(
            f"git {' '.join(args)} failed ({returncode})"
            + (f": {detail}" if detail else "")
        )


@dataclass(frozen=True, slots=True)
class CodingBacklogItem:
    task_id: str
    title: str
    repository: Path
    base_ref: str = "HEAD"
    allowed_paths: tuple[str, ...] = ()
    test_commands: tuple[tuple[str, ...], ...] = ()

    def __post_init__(self) -> None:
        if not self.task_id.strip() or not self.title.strip():
            raise ValueError("task_id and title must not be empty")
        if not self.allowed_paths:
            raise ValueError("allowed_paths must contain at least one scoped path")
        for value in self.allowed_paths:
            path = PurePosixPath(value.replace("\\", "/"))
            if path.is_absolute() or ".." in path.parts:
                raise ValueError(f"unsafe allowed path: {value}")
        for command in self.test_commands:
            if not command or not command[0].strip():
                raise ValueError("test commands must be non-empty argv tuples")


@dataclass(frozen=True, slots=True)
class CodingWorkerResult:
    task_id: str
    status: CodingWorkerStatus
    worktree: Path | None
    patch_file: Path | None
    approval_file: Path | None
    changed_files: tuple[str, ...]
    tests_run: tuple[str, ...]
    reason: str


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._") or "task"


class AutonomousCodingWorker:
    """Run one scoped coding task and stop at a tamper-evident owner gate.

    The worker creates a detached Git worktree, delegates edits to an injected
    builder, runs explicit argv-based tests and writes a binary Git patch. It
    deliberately has no push or merge operation.
    """

    def __init__(self, *, runner: BuilderRunner, workspace_root: Path) -> None:
        self.runner = runner
        self.workspace_root = Path(workspace_root).resolve()
        self.workspace_root.mkdir(parents=True, exist_ok=True)

    def run(self, item: CodingBacklogItem, worker_id: str) -> CodingWorkerResult:
        repository = Path(item.repository).resolve()
        worktree = self.workspace_root / _safe_name(item.task_id)
        if worktree.exists():
            return self._blocked(item, "task worktree already exists")

        try:
            base_commit = self._git(repository, "rev-parse", item.base_ref).strip()
            self._create_worktree(repository, worktree, base_commit, item.allowed_paths)
            prompt = self._prompt(item, worker_id, worktree)
            builder_result = self.runner(prompt, worktree)
            if not bool(getattr(builder_result, "success", True)):
                return self._blocked(item, "coding worker reported failure", worktree)

            if self._git(worktree, "rev-parse", "HEAD").strip() != base_commit:
                return self._blocked(item, "worker commits are forbidden before owner approval", worktree)

            changed = self._changed_files(worktree)
            if not changed:
                return self._blocked(item, "worker produced no tracked changes", worktree)
            outside = tuple(path for path in changed if not self._is_allowed(path, item.allowed_paths))
            if outside:
                return self._blocked(
                    item,
                    f"changes escaped approved scope: {', '.join(outside)}",
                    worktree,
                    changed,
                )

            removed_api = self._removed_public_python_api(
                worktree, base_commit, changed
            )
            if removed_api:
                detail = "; ".join(
                    f"{path}: {', '.join(names)}"
                    for path, names in removed_api
                )
                return self._blocked(
                    item,
                    "compatibility gate rejected removal of existing public "
                    f"Python API ({detail}). Preserve compatibility with a "
                    "re-export or additive implementation; broad new modules "
                    "and architecture remain allowed.",
                    worktree,
                    changed,
                )

            tests_run: list[str] = []
            for command in item.test_commands:
                test_env = os.environ.copy()
                test_env["PYTHONDONTWRITEBYTECODE"] = "1"
                core_path = worktree / "ahos_core"
                if core_path.is_dir():
                    # The long-running daemon is normally launched from the
                    # owner checkout and may therefore carry that checkout in
                    # PYTHONPATH.  Appending it lets an isolated test import a
                    # mixture of the candidate worktree and owner code.  Tests
                    # must resolve the package exclusively from the candidate.
                    test_env["PYTHONPATH"] = str(core_path)
                    test_env["PYTHONNOUSERSITE"] = "1"
                completed = subprocess.run(
                    command,
                    cwd=worktree,
                    env=test_env,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    check=False,
                )
                tests_run.append(" ".join(command))
                if completed.returncode:
                    detail = (completed.stderr or completed.stdout).strip()[-1000:]
                    return self._blocked(
                        item,
                        f"test failed ({completed.returncode}): {detail}",
                        worktree,
                        changed,
                        tuple(tests_run),
                    )

            # Tests are code too: they may create or modify files. Re-evaluate
            # the complete diff after every test before producing evidence.
            changed = self._changed_files(worktree)
            outside = tuple(path for path in changed if not self._is_allowed(path, item.allowed_paths))
            if outside:
                return self._blocked(
                    item,
                    f"tests changed files outside approved scope: {', '.join(outside)}",
                    worktree,
                    changed,
                    tuple(tests_run),
                )

            # Intent-to-add makes new files visible to ``git diff`` without
            # staging their contents or creating a commit.
            untracked = self._git(
                worktree, "ls-files", "--others", "--exclude-standard"
            ).splitlines()
            if untracked:
                self._git(worktree, "add", "--intent-to-add", "--", *untracked)
            patch = subprocess.run(
                ["git", "diff", "--binary", "--full-index", "HEAD", "--"],
                cwd=worktree,
                capture_output=True,
                check=True,
            ).stdout
            evidence_dir = worktree / ".ahos"
            evidence_dir.mkdir(exist_ok=True)
            patch_file = evidence_dir / "owner-review.patch"
            patch_file.write_bytes(patch)
            patch_sha256 = hashlib.sha256(patch).hexdigest()
            approval_file = evidence_dir / "OWNER-APPROVAL.json"
            approval_file.write_text(
                json.dumps(
                    {
                        "schema": "ahos.coding-owner-approval.v1",
                        "task_id": item.task_id,
                        "worker_id": worker_id,
                        "base_commit": base_commit,
                        "status": CodingWorkerStatus.WAITING_OWNER_APPROVAL.value,
                        "changed_files": list(changed),
                        "tests_run": tests_run,
                        "patch": patch_file.name,
                        "patch_sha256": patch_sha256,
                        "push_enabled": False,
                        "merge_enabled": False,
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            return CodingWorkerResult(
                task_id=item.task_id,
                status=CodingWorkerStatus.WAITING_OWNER_APPROVAL,
                worktree=worktree,
                patch_file=patch_file,
                approval_file=approval_file,
                changed_files=changed,
                tests_run=tuple(tests_run),
                reason="implementation and tests complete; owner approval required before integration",
            )
        except (OSError, subprocess.CalledProcessError, ValueError, GitCommandError) as exc:
            return self._blocked(item, f"coding pipeline failed: {type(exc).__name__}: {exc}", worktree if worktree.exists() else None)

    def _create_worktree(
        self,
        repository: Path,
        worktree: Path,
        base_commit: str,
        allowed_paths: Sequence[str],
    ) -> None:
        # On Windows, endpoint-security software may quarantine unrelated
        # administrative PowerShell files during a full checkout. Start with a
        # scoped checkout there instead of knowingly triggering that failure.
        if self._prefer_scoped_checkout():
            self._create_scoped_worktree(
                repository, worktree, base_commit, allowed_paths
            )
            return
        try:
            self._git(repository, "worktree", "add", "--detach", str(worktree), base_commit)
            return
        except GitCommandError as initial_error:
            # Endpoint-security products on Windows can quarantine an unrelated
            # PowerShell file while Git is checking out the complete tree. The
            # failed tree has never reached the builder, so it is safe to remove
            # and retry with only the owner-approved task scope materialized.
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(worktree)],
                cwd=repository,
                capture_output=True,
                text=True,
                check=False,
            )
            if worktree.exists():
                # This directory was absent immediately before this method and
                # the builder has not run, so it can only contain Git's partial
                # failed checkout. Remove it without touching user worktrees.
                shutil.rmtree(worktree)
            self._git(repository, "worktree", "prune")
            self._create_scoped_worktree(
                repository, worktree, base_commit, allowed_paths
            )

    @staticmethod
    def _prefer_scoped_checkout() -> bool:
        return os.name == "nt"

    def _create_scoped_worktree(
        self,
        repository: Path,
        worktree: Path,
        base_commit: str,
        allowed_paths: Sequence[str],
    ) -> None:
        self._git(
            repository,
            "worktree",
            "add",
            "--no-checkout",
            "--detach",
            str(worktree),
            base_commit,
        )
        patterns: list[str] = []
        for value in allowed_paths:
            normalized = value.replace("\\", "/").strip("/")
            patterns.extend((f"/{normalized}", f"/{normalized}/"))
        self._git(worktree, "sparse-checkout", "init", "--no-cone")
        self._git(worktree, "sparse-checkout", "set", "--no-cone", "--", *patterns)
        self._git(worktree, "reset", "--hard", base_commit)

    @staticmethod
    def _git(repository: Path, *args: str) -> str:
        completed = subprocess.run(
            ["git", *args],
            cwd=repository,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if completed.returncode:
            detail = (completed.stderr or completed.stdout).strip()[-2000:]
            raise GitCommandError(args, completed.returncode, detail)
        return completed.stdout

    def _changed_files(self, worktree: Path) -> tuple[str, ...]:
        tracked = self._git(worktree, "diff", "--name-only", "HEAD", "--").splitlines()
        untracked = self._git(
            worktree, "ls-files", "--others", "--exclude-standard"
        ).splitlines()
        return tuple(sorted(set(filter(None, tracked + untracked))))

    @staticmethod
    def _public_python_symbols(source: str) -> set[str]:
        """Return the module's statically visible public compatibility surface."""
        tree = ast.parse(source)
        symbols: set[str] = set()
        for node in tree.body:
            names: list[str] = []
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                names = [node.name]
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [alias.asname or alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.Assign):
                names = [target.id for target in node.targets if isinstance(target, ast.Name)]
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                names = [node.target.id]
            symbols.update(name for name in names if name and not name.startswith("_"))
        return symbols

    def _removed_public_python_api(
        self, worktree: Path, base_commit: str, changed: Sequence[str]
    ) -> tuple[tuple[str, tuple[str, ...]], ...]:
        """Detect accidental public API loss without restricting additive design."""
        removed: list[tuple[str, tuple[str, ...]]] = []
        for relative in changed:
            if not relative.endswith(".py"):
                continue
            baseline = subprocess.run(
                ["git", "show", f"{base_commit}:{relative}"],
                cwd=worktree,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            if baseline.returncode:
                continue  # New Python module: no compatibility surface to preserve.
            candidate = worktree / relative
            if not candidate.is_file():
                missing = self._public_python_symbols(baseline.stdout)
            else:
                try:
                    before = self._public_python_symbols(baseline.stdout)
                    after = self._public_python_symbols(
                        candidate.read_text(encoding="utf-8", errors="replace")
                    )
                except (OSError, SyntaxError):
                    continue  # The normal test/compile gate supplies the precise error.
                missing = before - after
            if missing:
                removed.append((relative, tuple(sorted(missing))))
        return tuple(removed)

    @staticmethod
    def _is_allowed(path: str, allowed_paths: Sequence[str]) -> bool:
        normalized = PurePosixPath(path.replace("\\", "/"))
        return any(
            normalized == PurePosixPath(root.replace("\\", "/"))
            or PurePosixPath(root.replace("\\", "/")) in normalized.parents
            for root in allowed_paths
        )

    @staticmethod
    def _prompt(item: CodingBacklogItem, worker_id: str, worktree: Path) -> str:
        return (
            f"You are AHOS coding worker {worker_id}.\n"
            f"Backlog item: {item.task_id} - {item.title}\n"
            f"Git worktree: {worktree}\n"
            f"Allowed paths: {', '.join(item.allowed_paths)}\n\n"
            "Implement the complete scoped item. You may add modules, classes, tests, "
            "and improve the architecture anywhere inside the allowed paths. Preserve "
            "all existing behavior and public import surfaces unless the owner task "
            "explicitly requires a migration; prefer additive integration or "
            "compatibility re-exports over replacing working subsystems. Do not commit, "
            "push, merge, deploy, "
            "access secrets, or change files outside the allowed paths. The AHOS "
            "supervisor runs the acceptance tests and prepares the owner-review patch."
        )

    @staticmethod
    def _blocked(
        item: CodingBacklogItem,
        reason: str,
        worktree: Path | None = None,
        changed_files: tuple[str, ...] = (),
        tests_run: tuple[str, ...] = (),
    ) -> CodingWorkerResult:
        return CodingWorkerResult(
            task_id=item.task_id,
            status=CodingWorkerStatus.BLOCKED,
            worktree=worktree,
            patch_file=None,
            approval_file=None,
            changed_files=changed_files,
            tests_run=tests_run,
            reason=reason,
        )
