from __future__ import annotations

from ahos.mission_orchestrator import (
    MissionStatus,
    MissionStepSpec,
    MultiWorkerMissionOrchestrator,
)
from ahos.virtual_workforce import VirtualWorkforceRegistry, default_virtual_workforce
from ahos.worker_runtime import (
    WorkerExecutionResult,
    local_pass_qa,
    make_local_text_executor,
)


def _planner(_mission_id: str, _objective: str, manager_id: str):
    assert manager_id == "mgr-software-01"
    return (
        MissionStepSpec(
            step_id="research",
            title="Research the requested feature",
            department="research",
            required_capabilities=frozenset({"research", "analysis"}),
        ),
        MissionStepSpec(
            step_id="build",
            title="Implement the researched feature",
            department="software",
            required_capabilities=frozenset({"python", "automation"}),
            depends_on=("research",),
        ),
        MissionStepSpec(
            step_id="finance",
            title="Prepare a zero-cost internal cost note",
            department="finance",
            required_capabilities=frozenset({"finance", "cost_tracking"}),
            depends_on=("build",),
        ),
    )


def test_manager_routes_multi_worker_mission_to_completion() -> None:
    registry = VirtualWorkforceRegistry(default_virtual_workforce())
    runtime = MultiWorkerMissionOrchestrator(
        registry,
        manager_planner=_planner,
        executors={
            "research-01": make_local_text_executor(
                lambda item, worker_id: "research findings ready"
            ),
            "dev-01": make_local_text_executor(
                lambda item, worker_id: (
                    "software implementation completed using prior research"
                )
            ),
            "finance-01": make_local_text_executor(
                lambda item, worker_id: "cost note: local execution USD 0"
            ),
        },
        qa_executor=local_pass_qa,
    )

    result = runtime.run(
        mission_id="mission-1",
        objective="Build a small internal automation",
        primary_department="software",
    )

    assert result.status is MissionStatus.COMPLETED
    assert result.manager_id == "mgr-software-01"
    assert [step.step.step_id for step in result.steps] == [
        "research",
        "build",
        "finance",
    ]
    assert [step.worker_id for step in result.steps] == [
        "research-01",
        "dev-01",
        "finance-01",
    ]
    assert all(step.qa_summary for step in result.steps)


def test_previous_step_summary_is_handed_to_next_worker() -> None:
    registry = VirtualWorkforceRegistry(default_virtual_workforce())
    seen_titles: list[str] = []

    def research_executor(item, worker_id):
        return WorkerExecutionResult(
            task_id=item.task_id,
            worker_id=worker_id,
            success=True,
            summary="important research context",
        )

    def dev_executor(item, worker_id):
        seen_titles.append(item.title)
        return WorkerExecutionResult(
            task_id=item.task_id,
            worker_id=worker_id,
            success=True,
            summary="built with context",
        )

    runtime = MultiWorkerMissionOrchestrator(
        registry,
        manager_planner=lambda *_: (
            MissionStepSpec(
                step_id="research",
                title="Research",
                department="research",
                required_capabilities=frozenset({"research"}),
            ),
            MissionStepSpec(
                step_id="build",
                title="Build",
                department="software",
                required_capabilities=frozenset({"python"}),
                depends_on=("research",),
            ),
        ),
        executors={
            "research-01": research_executor,
            "dev-01": dev_executor,
        },
        qa_executor=local_pass_qa,
    )

    result = runtime.run(
        mission_id="mission-context",
        objective="Use research to build",
        primary_department="software",
    )

    assert result.status is MissionStatus.COMPLETED
    assert seen_titles
    assert "important research context" in seen_titles[0]


def test_failed_worker_blocks_downstream_steps() -> None:
    registry = VirtualWorkforceRegistry(default_virtual_workforce())
    build_calls: list[str] = []

    def fail_research(item, worker_id):
        return WorkerExecutionResult(
            task_id=item.task_id,
            worker_id=worker_id,
            success=False,
            summary="research failed",
        )

    def build_executor(item, worker_id):
        build_calls.append(item.task_id)
        return WorkerExecutionResult(
            task_id=item.task_id,
            worker_id=worker_id,
            success=True,
            summary="should not run",
        )

    runtime = MultiWorkerMissionOrchestrator(
        registry,
        manager_planner=lambda *_: (
            MissionStepSpec(
                step_id="research",
                title="Research",
                department="research",
                required_capabilities=frozenset({"research"}),
            ),
            MissionStepSpec(
                step_id="build",
                title="Build",
                department="software",
                required_capabilities=frozenset({"python"}),
                depends_on=("research",),
            ),
        ),
        executors={
            "research-01": fail_research,
            "dev-01": build_executor,
        },
        qa_executor=local_pass_qa,
    )

    result = runtime.run(
        mission_id="mission-fail",
        objective="Blocked mission",
        primary_department="software",
    )

    assert result.status is MissionStatus.BLOCKED
    assert len(result.steps) == 1
    assert build_calls == []


def test_unapproved_paid_step_blocks_mission_before_executor() -> None:
    registry = VirtualWorkforceRegistry(default_virtual_workforce())
    calls: list[str] = []

    def executor(item, worker_id):
        calls.append(item.task_id)
        return WorkerExecutionResult(
            task_id=item.task_id,
            worker_id=worker_id,
            success=True,
            summary="should not run",
        )

    runtime = MultiWorkerMissionOrchestrator(
        registry,
        manager_planner=lambda *_: (
            MissionStepSpec(
                step_id="paid",
                title="Use paid AI",
                department="software",
                required_capabilities=frozenset({"python"}),
                estimated_cost_usd=0.01,
            ),
        ),
        executors={"dev-01": executor},
        qa_executor=local_pass_qa,
    )

    result = runtime.run(
        mission_id="mission-paid",
        objective="Paid step",
        primary_department="software",
    )

    assert result.status is MissionStatus.BLOCKED
    assert calls == []


def test_dependency_cycle_is_rejected() -> None:
    registry = VirtualWorkforceRegistry(default_virtual_workforce())

    runtime = MultiWorkerMissionOrchestrator(
        registry,
        manager_planner=lambda *_: (
            MissionStepSpec(
                step_id="a",
                title="A",
                department="software",
                required_capabilities=frozenset({"python"}),
                depends_on=("b",),
            ),
            MissionStepSpec(
                step_id="b",
                title="B",
                department="software",
                required_capabilities=frozenset({"python"}),
                depends_on=("a",),
            ),
        ),
        executors={},
        qa_executor=local_pass_qa,
    )

    result = runtime.run(
        mission_id="mission-cycle",
        objective="Cycle",
        primary_department="software",
    )

    assert result.status is MissionStatus.BLOCKED
    assert "dependency cycle" in result.reason
