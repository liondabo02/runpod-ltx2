from pathlib import Path

import pytest

from miniverse.execution import MiniverseExecutionPipeline
from miniverse.openhands_builder import BuilderResult
from miniverse.policy import OwnerPolicy


class FakeOrchestrator:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def analyze(self, task: str) -> str:
        self.calls.append(task)
        if "PHASE: PREFLIGHT ONLY" in task:
            return "verified preflight"
        return "qa approved for PR only"


class FakeBuilder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Path]] = []

    def run(self, task: str, workspace: str | Path) -> BuilderResult:
        path = Path(workspace)
        self.calls.append((task, path))
        return BuilderResult(
            summary="minimal fix created",
            tests_run=("pytest -q: passed",),
            changed_files=("workflows/minimal_i2v.json",),
            rollback="revert workspace diff",
            remaining_risks=("paid GPU E2E not run",),
            estimated_cost_usd=0.0,
        )


@pytest.mark.asyncio
async def test_execute_runs_preflight_builder_and_qa(tmp_path: Path):
    orchestrator = FakeOrchestrator()
    builder = FakeBuilder()
    pipeline = MiniverseExecutionPipeline(
        policy=OwnerPolicy(),
        orchestrator=orchestrator,
        builder=builder,
    )

    result = await pipeline.execute("fix the isolated minimal I2V workflow", tmp_path)

    assert result.preflight_report == "verified preflight"
    assert result.builder.summary == "minimal fix created"
    assert result.qa_report == "qa approved for PR only"
    assert len(orchestrator.calls) == 2
    assert len(builder.calls) == 1
    assert builder.calls[0][1] == tmp_path.resolve()


@pytest.mark.asyncio
async def test_execute_blocks_paid_action_before_builder(tmp_path: Path):
    orchestrator = FakeOrchestrator()
    builder = FakeBuilder()
    pipeline = MiniverseExecutionPipeline(
        policy=OwnerPolicy(),
        orchestrator=orchestrator,
        builder=builder,
    )

    with pytest.raises(PermissionError, match="Owner approval required"):
        await pipeline.execute("run a paid RunPod GPU job", tmp_path)

    assert len(orchestrator.calls) == 1
    assert builder.calls == []


@pytest.mark.asyncio
async def test_execute_rejects_missing_workspace(tmp_path: Path):
    pipeline = MiniverseExecutionPipeline(
        policy=OwnerPolicy(),
        orchestrator=FakeOrchestrator(),
        builder=FakeBuilder(),
    )

    with pytest.raises(ValueError, match="Workspace does not exist"):
        await pipeline.execute("safe code review task", tmp_path / "missing")
