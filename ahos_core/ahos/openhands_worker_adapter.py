from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .worker_runtime import WorkerExecutionResult
from .workforce_execution import WorkItem


BuilderRunner = Callable[[str, Path], Any]


def _safe_task_dir(task_id: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", task_id).strip("._")
    return value or "task"


def _tuple_of_strings(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    try:
        return tuple(str(item) for item in value)
    except TypeError:
        return (str(value),)


@dataclass(slots=True)
class OpenHandsWorkerAdapter:
    """Bridge an AHOS virtual employee to an injected OpenHands-style runner.

    The runner is injected so local tests stay zero-cost. Protected actions,
    including paid AI work, fail closed unless owner approval is explicit.
    """

    runner: BuilderRunner
    workspace_root: Path

    def __post_init__(self) -> None:
        self.workspace_root = Path(self.workspace_root)
        self.workspace_root.mkdir(parents=True, exist_ok=True)

    def __call__(self, item: WorkItem, worker_id: str) -> WorkerExecutionResult:
        protected_action = any(
            (
                item.external_side_effect,
                item.destructive,
                item.touches_secrets,
                item.estimated_cost_usd > 0,
            )
        )
        if protected_action and not item.owner_approved:
            return WorkerExecutionResult(
                task_id=item.task_id,
                worker_id=worker_id,
                success=False,
                summary="execution blocked by local safety gate",
            )

        workspace = self.workspace_root / _safe_task_dir(item.task_id)
        workspace.mkdir(parents=True, exist_ok=True)

        prompt = self._prompt(item=item, worker_id=worker_id, workspace=workspace)

        try:
            result = self.runner(prompt, workspace)
        except Exception as exc:
            return WorkerExecutionResult(
                task_id=item.task_id,
                worker_id=worker_id,
                success=False,
                summary=f"builder execution failed: {type(exc).__name__}: {exc}",
            )

        result_success = getattr(result, "success", True)
        summary = str(
            getattr(result, "summary", None)
            or getattr(result, "change_summary", None)
            or "builder completed"
        )
        changed_files = _tuple_of_strings(
            getattr(result, "changed_files", None)
            or getattr(result, "artifacts", None)
        )
        tests_run = _tuple_of_strings(getattr(result, "tests_run", None))

        return WorkerExecutionResult(
            task_id=item.task_id,
            worker_id=worker_id,
            success=bool(result_success),
            summary=summary,
            artifacts=changed_files,
            tests_run=tests_run,
        )

    @staticmethod
    def _prompt(*, item: WorkItem, worker_id: str, workspace: Path) -> str:
        capabilities = ", ".join(sorted(item.required_capabilities)) or "none"
        return (
            f"You are AHOS virtual worker {worker_id}.\n"
            f"Task ID: {item.task_id}\n"
            f"Task: {item.title}\n"
            f"Department: {item.department}\n"
            f"Required capabilities: {capabilities}\n"
            f"Workspace: {workspace}\n\n"
            "Work only inside the provided workspace. "
            "Do not publish, message, purchase, deploy externally, access secrets, "
            "or perform destructive actions. Run relevant local tests. "
            "Return a concise summary, changed files, tests run, and remaining risks."
        )


def make_builder_runner(builder: Any) -> BuilderRunner:
    """Wrap a builder object exposing run(task=..., workspace=...)."""

    def _run(prompt: str, workspace: Path) -> Any:
        return builder.run(task=prompt, workspace=workspace)

    return _run
