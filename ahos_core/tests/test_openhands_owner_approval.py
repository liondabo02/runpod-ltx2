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


def test_owner_approved_paid_work_can_reach_runner(tmp_path: Path) -> None:
    calls: list[str] = []

    def runner(_prompt: str, _workspace: Path) -> FakeBuilderResult:
        calls.append("called")
        return FakeBuilderResult("ok", ("x.txt",), ())

    adapter = OpenHandsWorkerAdapter(runner=runner, workspace_root=tmp_path)
    item = WorkItem(
        task_id="approved-paid",
        title="Tiny approved paid smoke",
        department="software",
        required_capabilities=frozenset({"python"}),
        estimated_cost_usd=0.02,
        owner_approved=True,
    )

    result = adapter(item, "dev-01-live")

    assert result.success is True
    assert calls == ["called"]


def test_unapproved_paid_work_remains_blocked(tmp_path: Path) -> None:
    calls: list[str] = []

    def runner(_prompt: str, _workspace: Path) -> FakeBuilderResult:
        calls.append("called")
        return FakeBuilderResult("ok", (), ())

    adapter = OpenHandsWorkerAdapter(runner=runner, workspace_root=tmp_path)
    item = WorkItem(
        task_id="unapproved-paid",
        title="Unapproved paid work",
        department="software",
        required_capabilities=frozenset({"python"}),
        estimated_cost_usd=0.02,
    )

    result = adapter(item, "dev-01-live")

    assert result.success is False
    assert calls == []


def test_unapproved_external_work_remains_blocked(tmp_path: Path) -> None:
    calls: list[str] = []

    def runner(_prompt: str, _workspace: Path) -> FakeBuilderResult:
        calls.append("called")
        return FakeBuilderResult("ok", (), ())

    adapter = OpenHandsWorkerAdapter(runner=runner, workspace_root=tmp_path)
    item = WorkItem(
        task_id="unapproved-external",
        title="External work",
        department="software",
        required_capabilities=frozenset({"python"}),
        external_side_effect=True,
    )

    result = adapter(item, "dev-01-live")

    assert result.success is False
    assert calls == []
