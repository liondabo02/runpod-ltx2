from __future__ import annotations

import pytest

from ahos.virtual_workforce import (
    VirtualWorkforceRegistry,
    WorkerProfile,
    WorkerRole,
    WorkerStatus,
    default_virtual_workforce,
)


def test_default_workforce_contains_core_departments() -> None:
    workforce = default_virtual_workforce()
    departments = {worker.department for worker in workforce}

    assert {
        "software",
        "quality",
        "research",
        "infrastructure",
        "data",
        "creative",
        "marketing",
        "sales",
        "finance",
        "operations",
        "support",
    }.issubset(departments)


def test_capability_matching_and_single_task_lease() -> None:
    registry = VirtualWorkforceRegistry(default_virtual_workforce())

    matches = registry.matching_workers({"python", "api"}, department="software")
    assert matches
    assert matches[0].profile.worker_id == "dev-01"

    registry.assign("dev-01", "task-1")
    assert registry.get("dev-01").status is WorkerStatus.ASSIGNED
    assert registry.get("dev-01").available_slots == 0

    with pytest.raises(RuntimeError):
        registry.assign("dev-01", "task-2")

    registry.release("dev-01", "task-1")
    assert registry.get("dev-01").status is WorkerStatus.IDLE


def test_paid_ai_is_denied_by_default() -> None:
    registry = VirtualWorkforceRegistry(default_virtual_workforce())

    matches = registry.matching_workers(
        {"python"},
        department="software",
        estimated_cost_usd=0.01,
    )
    assert matches == ()


def test_budgeted_worker_can_be_gated_and_charged() -> None:
    worker = WorkerProfile(
        worker_id="paid-dev",
        name="Paid Dev",
        role=WorkerRole.SOFTWARE_ENGINEER,
        department="software",
        capabilities=frozenset({"python"}),
        daily_budget_usd=0.05,
        can_use_paid_ai=True,
    )
    registry = VirtualWorkforceRegistry((worker,))

    assert registry.matching_workers({"python"}, estimated_cost_usd=0.02)
    registry.assign("paid-dev", "task-1", estimated_cost_usd=0.02)
    registry.record_spend("paid-dev", 0.02)

    with pytest.raises(RuntimeError):
        registry.record_spend("paid-dev", 0.04)


def test_pause_blocks_assignment() -> None:
    registry = VirtualWorkforceRegistry(default_virtual_workforce())
    registry.pause("qa-01")

    assert registry.get("qa-01").status is WorkerStatus.PAUSED
    assert registry.matching_workers({"qa"}) == ()

    registry.resume("qa-01")
    assert registry.get("qa-01").status is WorkerStatus.IDLE
