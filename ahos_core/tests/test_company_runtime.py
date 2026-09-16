from __future__ import annotations

import json
from pathlib import Path

from ahos.autonomous_company import (
    CompanyLoop,
    PersistentMissionQueue,
    QueueStatus,
)
from ahos.company_runtime import OrchestratedMissionExecutor
from ahos.mission_orchestrator import (
    MissionStatus,
    MissionStepSpec,
    MultiWorkerMissionOrchestrator,
)
from ahos.virtual_workforce import (
    VirtualWorkforceRegistry,
    default_virtual_workforce,
)
from ahos.worker_runtime import local_pass_qa, make_local_text_executor


def _runtime() -> MultiWorkerMissionOrchestrator:
    registry = VirtualWorkforceRegistry(default_virtual_workforce())

    def planner(_mission_id: str, _objective: str, _manager_id: str):
        return (
            MissionStepSpec(
                step_id="research",
                title="Research requirements",
                department="research",
                required_capabilities=frozenset({"research"}),
            ),
            MissionStepSpec(
                step_id="build",
                title="Build from research",
                department="software",
                required_capabilities=frozenset({"python"}),
                depends_on=("research",),
            ),
        )

    return MultiWorkerMissionOrchestrator(
        registry,
        manager_planner=planner,
        executors={
            "research-01": make_local_text_executor(
                lambda item, worker_id: "research handoff ready"
            ),
            "dev-01": make_local_text_executor(
                lambda item, worker_id: "prototype ready"
            ),
        },
        qa_executor=local_pass_qa,
    )


def test_queue_dispatches_into_full_orchestrator(tmp_path: Path) -> None:
    queue = PersistentMissionQueue(tmp_path / "missions.db")
    queue.enqueue(
        mission_id="m1",
        objective="research then build",
        primary_department="software",
    )

    loop = CompanyLoop(
        queue=queue,
        executor=OrchestratedMissionExecutor(_runtime()),
        owner="company-loop",
    )

    final = loop.run_once()

    assert final is not None
    assert final.status is QueueStatus.COMPLETED
    assert final.result_json is not None

    payload = json.loads(final.result_json)
    assert payload["status"] == "completed"
    assert [step["worker_id"] for step in payload["steps"]] == [
        "research-01",
        "dev-01",
    ]


def test_queue_preserves_primary_department_for_manager_selection(
    tmp_path: Path,
) -> None:
    queue = PersistentMissionQueue(tmp_path / "missions.db")
    queue.enqueue(
        mission_id="m2",
        objective="software mission",
        primary_department="software",
    )

    executor = OrchestratedMissionExecutor(_runtime())
    claimed = queue.claim_next(owner="manual")

    assert claimed is not None
    result = executor(claimed)

    assert result.status is MissionStatus.COMPLETED
    assert result.manager_id == "mgr-software-01"


def test_blocked_orchestrator_result_becomes_blocked_queue_item(
    tmp_path: Path,
) -> None:
    registry = VirtualWorkforceRegistry(default_virtual_workforce())

    runtime = MultiWorkerMissionOrchestrator(
        registry,
        manager_planner=lambda *_: (
            MissionStepSpec(
                step_id="paid",
                title="Paid protected work",
                department="software",
                required_capabilities=frozenset({"python"}),
                estimated_cost_usd=0.01,
            ),
        ),
        executors={
            "dev-01": make_local_text_executor(
                lambda item, worker_id: "should not run"
            ),
        },
        qa_executor=local_pass_qa,
    )

    queue = PersistentMissionQueue(tmp_path / "missions.db")
    queue.enqueue(
        mission_id="m3",
        objective="protected mission",
        primary_department="software",
        max_attempts=3,
    )

    loop = CompanyLoop(
        queue=queue,
        executor=OrchestratedMissionExecutor(runtime),
        owner="company-loop",
    )
    final = loop.run_once()

    assert final is not None
    assert final.status is QueueStatus.BLOCKED
    assert final.attempts == 1
