from __future__ import annotations

import pytest

from ahos.work_order import WorkOrderStatus, WorkOrderStore


def test_create_persistent_work_order(tmp_path) -> None:
    store = WorkOrderStore(tmp_path / "work_orders.json")
    order = store.create(
        work_order_id="wo-1",
        venture_id="v-1",
        mission_id="m-1",
        capability_requirements=("software.build_and_test",),
        priority=5,
        budget_ceiling_usd=500,
        routing_department="software",
        routing_score=120,
        timestamp="2026-09-16T12:00:00+00:00",
    )

    assert order.status is WorkOrderStatus.PENDING
    assert order.audit_correlation_id == "work-order:wo-1"
    assert WorkOrderStore(tmp_path / "work_orders.json").get("wo-1") == order


def test_duplicate_ids_are_rejected(tmp_path) -> None:
    store = WorkOrderStore(tmp_path / "work_orders.json")
    store.create(
        work_order_id="wo-1",
        venture_id="v-1",
        mission_id="m-1",
    )

    with pytest.raises(ValueError, match="duplicate work_order_id"):
        store.create(
            work_order_id="wo-1",
            venture_id="v-2",
            mission_id="m-2",
        )


def test_valid_transition_path(tmp_path) -> None:
    store = WorkOrderStore(tmp_path / "work_orders.json")
    store.create(
        work_order_id="wo-2",
        venture_id="v-1",
        mission_id="m-2",
    )

    assert store.transition("wo-2", WorkOrderStatus.READY).status is WorkOrderStatus.READY
    assert (
        store.transition("wo-2", WorkOrderStatus.IN_PROGRESS).status
        is WorkOrderStatus.IN_PROGRESS
    )
    assert (
        store.transition("wo-2", WorkOrderStatus.COMPLETED).status
        is WorkOrderStatus.COMPLETED
    )


def test_invalid_transition_is_rejected(tmp_path) -> None:
    store = WorkOrderStore(tmp_path / "work_orders.json")
    store.create(
        work_order_id="wo-3",
        venture_id="v-1",
        mission_id="m-3",
    )

    with pytest.raises(ValueError, match="invalid work order transition"):
        store.transition("wo-3", WorkOrderStatus.COMPLETED)


def test_ready_respects_dependencies_and_priority(tmp_path) -> None:
    store = WorkOrderStore(tmp_path / "work_orders.json")
    store.create(
        work_order_id="wo-a",
        venture_id="v-1",
        mission_id="m-a",
        priority=1,
    )
    store.create(
        work_order_id="wo-b",
        venture_id="v-1",
        mission_id="m-b",
        priority=10,
        dependencies=("wo-a",),
    )
    store.create(
        work_order_id="wo-c",
        venture_id="v-1",
        mission_id="m-c",
        priority=5,
    )

    first = store.ready()
    assert [item.work_order_id for item in first] == ["wo-c", "wo-a"]

    second = store.ready(completed_work_order_ids=("wo-a",))
    assert [item.work_order_id for item in second] == ["wo-b", "wo-c", "wo-a"]
