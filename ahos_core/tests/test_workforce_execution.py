from __future__ import annotations

from ahos.virtual_workforce import VirtualWorkforceRegistry, default_virtual_workforce
from ahos.workforce_execution import (
    VirtualWorkforceDispatcher,
    WorkItem,
    WorkStage,
    manager_for_department,
)


def test_software_task_routes_to_software_worker() -> None:
    registry = VirtualWorkforceRegistry(default_virtual_workforce())
    dispatcher = VirtualWorkforceDispatcher(registry)

    decision = dispatcher.assign(
        WorkItem(
            task_id="task-1",
            title="Build Python API automation",
            department="software",
            required_capabilities=frozenset({"python", "api", "automation"}),
        )
    )

    assert decision.stage is WorkStage.ASSIGNED
    assert decision.worker_id == "dev-01"


def test_paid_or_external_task_is_blocked_for_owner_approval() -> None:
    registry = VirtualWorkforceRegistry(default_virtual_workforce())
    dispatcher = VirtualWorkforceDispatcher(registry)

    paid = dispatcher.assign(
        WorkItem(
            task_id="task-paid",
            title="Use paid model",
            department="software",
            required_capabilities=frozenset({"python"}),
            estimated_cost_usd=0.01,
        )
    )
    external = dispatcher.assign(
        WorkItem(
            task_id="task-external",
            title="Publish result",
            department="marketing",
            required_capabilities=frozenset({"marketing"}),
            external_side_effect=True,
        )
    )

    assert paid.stage is WorkStage.BLOCKED
    assert paid.owner_approval_required is True
    assert external.stage is WorkStage.BLOCKED
    assert external.owner_approval_required is True


def test_worker_phase_hands_task_to_qa() -> None:
    registry = VirtualWorkforceRegistry(default_virtual_workforce())
    dispatcher = VirtualWorkforceDispatcher(registry)

    assigned = dispatcher.assign(
        WorkItem(
            task_id="task-qa",
            title="Implement feature",
            department="software",
            required_capabilities=frozenset({"python"}),
        )
    )
    ready = dispatcher.complete_worker_phase("task-qa", assigned.worker_id or "")
    qa = dispatcher.assign_qa("task-qa")
    done = dispatcher.complete_qa(
        "task-qa",
        qa.qa_worker_id or "",
        passed=True,
    )

    assert ready.stage is WorkStage.READY_FOR_QA
    assert qa.qa_worker_id == "qa-01"
    assert done.stage is WorkStage.COMPLETED


def test_worker_slot_prevents_double_assignment() -> None:
    registry = VirtualWorkforceRegistry(default_virtual_workforce())
    dispatcher = VirtualWorkforceDispatcher(registry)

    first = dispatcher.assign(
        WorkItem(
            task_id="task-a",
            title="First task",
            department="software",
            required_capabilities=frozenset({"python"}),
        )
    )
    second = dispatcher.assign(
        WorkItem(
            task_id="task-b",
            title="Second task",
            department="software",
            required_capabilities=frozenset({"python"}),
        )
    )

    assert first.stage is WorkStage.ASSIGNED
    assert second.stage is WorkStage.BLOCKED


def test_department_manager_lookup() -> None:
    registry = VirtualWorkforceRegistry(default_virtual_workforce())
    manager = manager_for_department(registry.all(), "software")

    assert manager is not None
    assert manager.profile.worker_id == "mgr-software-01"
