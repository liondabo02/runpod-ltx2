from __future__ import annotations

from dataclasses import dataclass

from ahos.costs import CostGuard
from .model_routing import ModelEndpoint, ZeroCostSeparationRouter


@dataclass(frozen=True, slots=True)
class CostAuditReport:
    zero_budget_blocks_paid: bool
    zero_cost_routing_only: bool
    total_allowed_paid_usd: float
    passed: bool


def run_zero_cost_audit() -> CostAuditReport:
    guard = CostGuard(daily_budget_usd=0.0)
    zero_allowed = guard.can_spend(0.0)
    paid_blocked = not guard.can_spend(0.000001)
    raised = False
    try:
        guard.record(0.01)
    except RuntimeError:
        raised = True

    route = ZeroCostSeparationRouter().select((
        ModelEndpoint("local-builder", "builder", 0.0),
        ModelEndpoint("free-reviewer", "reviewer", 0.0),
        ModelEndpoint("paid", "both", 0.01),
    ))
    routing_ok = route.allowed and "paid" not in {route.builder, route.reviewer}
    passed = zero_allowed and paid_blocked and raised and routing_ok and guard.spent_usd == 0.0
    return CostAuditReport(
        zero_budget_blocks_paid=paid_blocked and raised,
        zero_cost_routing_only=routing_ok,
        total_allowed_paid_usd=guard.spent_usd,
        passed=passed,
    )
