from __future__ import annotations

import json

import pytest

from ahos import (
    ActionRequest,
    AgentRegistry,
    AuditLog,
    AuthorityLevel,
    CostGuard,
    Event,
    EventBus,
    GovernancePolicy,
)


def test_governance_allows_local_reversible_build() -> None:
    decision = GovernancePolicy().evaluate(
        ActionRequest(name="run unit tests", authority=AuthorityLevel.B)
    )
    assert decision.allowed is True
    assert decision.owner_approval_required is False


def test_governance_blocks_external_or_paid_actions() -> None:
    decision = GovernancePolicy().evaluate(
        ActionRequest(
            name="publish and run paid compute",
            authority=AuthorityLevel.C,
            estimated_cost_usd=0.01,
            external_side_effect=True,
        )
    )
    assert decision.allowed is False
    assert decision.owner_approval_required is True
    assert any("paid action" in reason for reason in decision.reasons)


def test_agent_registry_prevents_duplicate_agent() -> None:
    registry = AgentRegistry()
    registry.acquire("builder", "mission-1")
    with pytest.raises(RuntimeError):
        registry.acquire("builder", "mission-2")
    registry.release("builder", "mission-1")
    assert registry.is_busy("builder") is False


def test_event_bus_delivers_subscribed_event() -> None:
    seen: list[str] = []
    bus = EventBus()
    bus.subscribe("mission.completed", lambda event: seen.append(event.payload["id"]))
    bus.publish(Event("mission.completed", {"id": "m-1"}))
    assert seen == ["m-1"]


def test_cost_guard_enforces_budget() -> None:
    guard = CostGuard(daily_budget_usd=0.05)
    guard.record(0.02)
    assert guard.can_spend(0.03) is True
    assert guard.can_spend(0.031) is False
    with pytest.raises(RuntimeError):
        guard.record(0.031)


def test_audit_log_is_append_only_jsonl(tmp_path) -> None:
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    log.append("mission.started", {"id": "m-1"})
    log.append("mission.completed", {"id": "m-1"})
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert [item["event_type"] for item in records] == ["mission.started", "mission.completed"]
