from __future__ import annotations

import pytest

from ahos.virtual_workforce import (
    VirtualWorkforceRegistry,
    WorkerProfile,
    WorkerRole,
)
from ahos.workforce_execution import VirtualWorkforceDispatcher, WorkItem


def _worker(**overrides) -> WorkerProfile:
    base = dict(
        worker_id="w1",
        name="w1",
        role=WorkerRole.SOFTWARE_ENGINEER,
        department="oyun",
        capabilities=frozenset({"code"}),
    )
    base.update(overrides)
    return WorkerProfile(**base)


def test_paid_ai_is_disabled_by_default() -> None:
    profile = _worker()
    assert profile.can_use_paid_ai is False
    assert profile.daily_budget_usd == 0.0


def test_daily_budget_cannot_be_exceeded() -> None:
    registry = VirtualWorkforceRegistry()
    registry.register(_worker(daily_budget_usd=0.01))

    registry.record_spend("w1", 0.005)
    with pytest.raises(RuntimeError):
        registry.record_spend("w1", 0.02)


def test_budget_exhausted_worker_gets_no_new_assignment() -> None:
    registry = VirtualWorkforceRegistry()
    registry.register(_worker(daily_budget_usd=0.01))
    registry.record_spend("w1", 0.01)

    dispatcher = VirtualWorkforceDispatcher(registry)
    item = WorkItem(
        task_id="t1",
        title="iş",
        department="oyun",
        required_capabilities=frozenset({"code"}),
        estimated_cost_usd=0.005,
    )

    decision = dispatcher.assign(item)

    assert decision.worker_id is None
    assert decision.stage.value == "blocked"
