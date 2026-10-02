from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ahos.openhands_worker_adapter import OpenHandsWorkerAdapter
from ahos.workforce_execution import WorkItem


@dataclass
class FakeBuilderResult:
    summary: str
    changed_files: tuple[str, ...]
    tests_run: tuple[str, ...]
    success: bool = True


def _item(task_id: str = "task-1") -> WorkItem:
    return WorkItem(
        task_id=task_id,
        title="Implement Python API automation",
        department="software",
        required_capabilities=frozenset({"python", "api", "automation"}),
    )


def test_adapter_maps_builder_result_to_worker_result(tmp_path: Path) -> None:
    calls: list[tuple[str, Path]] = []

    def runner(prompt: str, workspace: Path) -> FakeBuilderResult:
        calls.append((prompt, workspace))
        (workspace / "result.txt").write_text("ok", encoding="utf-8")
        return FakeBuilderResult(
            summary="implemented feature",
            changed_files=("result.txt",),
            tests_run=("pytest -q",),
        )

    adapter = OpenHandsWorkerAdapter(runner=runner, workspace_root=tmp_path)
    result = adapter(_item(), "dev-01")

    assert result.success is True
    assert result.summary == "implemented feature"
    assert result.artifacts == ("result.txt",)
    assert result.tests_run == ("pytest -q",)
    assert calls
    assert "dev-01" in calls[0][0]
    assert calls[0][1].is_dir()


def test_adapter_fails_closed_on_runner_exception(tmp_path: Path) -> None:
    def runner(_prompt: str, _workspace: Path):
        raise RuntimeError("boom")

    adapter = OpenHandsWorkerAdapter(runner=runner, workspace_root=tmp_path)
    result = adapter(_item(), "dev-01")

    assert result.success is False
    assert "RuntimeError" in result.summary


def test_adapter_sanitizes_task_workspace(tmp_path: Path) -> None:
    seen: list[Path] = []

    def runner(_prompt: str, workspace: Path) -> FakeBuilderResult:
        seen.append(workspace)
        return FakeBuilderResult("ok", (), ())

    adapter = OpenHandsWorkerAdapter(runner=runner, workspace_root=tmp_path)
    result = adapter(_item("../../escape"), "dev-01")

    assert result.success is True
    assert seen[0].parent == tmp_path
    assert ".." not in seen[0].name


def test_adapter_blocks_paid_or_external_work_even_if_called_directly(tmp_path: Path) -> None:
    calls: list[str] = []

    def runner(_prompt: str, _workspace: Path) -> FakeBuilderResult:
        calls.append("called")
        return FakeBuilderResult("ok", (), ())

    adapter = OpenHandsWorkerAdapter(runner=runner, workspace_root=tmp_path)

    paid = WorkItem(
        task_id="paid",
        title="Paid task",
        department="software",
        required_capabilities=frozenset({"python"}),
        estimated_cost_usd=0.01,
    )
    external = WorkItem(
        task_id="external",
        title="External task",
        department="software",
        required_capabilities=frozenset({"python"}),
        external_side_effect=True,
    )

    assert adapter(paid, "dev-01").success is False
    assert adapter(external, "dev-01").success is False
    assert calls == []
