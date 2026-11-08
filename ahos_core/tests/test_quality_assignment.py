from __future__ import annotations

from ahos import worker_metrics
from ahos.virtual_workforce import (
    VirtualWorkforceRegistry,
    WorkerProfile,
    WorkerRole,
)
from ahos.workforce_execution import VirtualWorkforceDispatcher, WorkItem


def _worker(worker_id: str) -> WorkerProfile:
    return WorkerProfile(
        worker_id=worker_id,
        name=worker_id,
        role=WorkerRole.SOFTWARE_ENGINEER,
        department="oyun",
        capabilities=frozenset({"code"}),
    )


def _item() -> WorkItem:
    return WorkItem(
        task_id="t-1",
        title="iş",
        department="oyun",
        required_capabilities=frozenset({"code"}),
    )


def test_assignment_prefers_the_more_reliable_worker(tmp_path) -> None:
    worker_metrics.configure(tmp_path)
    # engineer-a: 3 başarı, 3 başarısızlık → %50
    for index in range(3):
        worker_metrics.record_here(
            worker_id="engineer-a",
            mission_id=f"a-{index}",
            step_id="produce",
            department="oyun",
            success=index % 2 == 0,
            duration_ms=10.0,
        )
    # engineer-b: 3 başarı → %100
    for index in range(3):
        worker_metrics.record_here(
            worker_id="engineer-b",
            mission_id=f"b-{index}",
            step_id="produce",
            department="oyun",
            success=True,
            duration_ms=10.0,
        )

    registry = VirtualWorkforceRegistry()
    registry.register(_worker("engineer-a"))
    registry.register(_worker("engineer-b"))
    dispatcher = VirtualWorkforceDispatcher(registry)

    decision = dispatcher.assign(_item())

    assert decision.worker_id == "engineer-b"


def test_assignment_falls_back_without_metrics(tmp_path) -> None:
    worker_metrics.configure(tmp_path)
    registry = VirtualWorkforceRegistry()
    registry.register(_worker("engineer-a"))
    registry.register(_worker("engineer-b"))
    dispatcher = VirtualWorkforceDispatcher(registry)

    decision = dispatcher.assign(_item())

    assert decision.worker_id in {"engineer-a", "engineer-b"}
    assert decision.stage.value == "assigned"
