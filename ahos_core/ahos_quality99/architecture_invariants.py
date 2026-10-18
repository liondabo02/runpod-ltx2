from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from ahos.control_center import ControlCenterState, serve
from ahos.costs import CostGuard
from ahos.governance import ActionRequest, AuthorityLevel, GovernancePolicy
from ahos_quality99.queue_stress import run_synthetic_queue_stress
from ahos_quality99.process_recovery_e2e import run_process_recovery_e2e


@dataclass(frozen=True, slots=True)
class ArchitectureInvariantReport:
    owner_boundary: bool
    localhost_boundary: bool
    zero_cost_boundary: bool
    durable_queue: bool
    recovery_boundary: bool
    passed: bool


def run_architecture_invariants() -> ArchitectureInvariantReport:
    """Validate existing AHOS boundaries; creates no new orchestrator."""
    policy = GovernancePolicy()
    owner_boundary = all(
        not policy.evaluate(request).allowed
        for request in (
            ActionRequest("external", AuthorityLevel.C, external_side_effect=True),
            ActionRequest("destructive", AuthorityLevel.D, destructive=True),
            ActionRequest("paid", AuthorityLevel.B, estimated_cost_usd=0.01),
        )
    )

    with TemporaryDirectory(prefix="ahos-q99-architecture-") as tmp:
        state = ControlCenterState(Path(tmp) / "runtime")
        try:
            serve(state, host="0.0.0.0", port=0)
            localhost_boundary = False
        except ValueError:
            localhost_boundary = True

    guard = CostGuard(daily_budget_usd=0.0)
    zero_cost_boundary = guard.can_spend(0.0) and not guard.can_spend(0.000001)

    queue = run_synthetic_queue_stress(task_count=100)
    durable_queue = queue.passed
    recovery = run_process_recovery_e2e()
    recovery_boundary = recovery.passed

    return ArchitectureInvariantReport(
        owner_boundary=owner_boundary,
        localhost_boundary=localhost_boundary,
        zero_cost_boundary=zero_cost_boundary,
        durable_queue=durable_queue,
        recovery_boundary=recovery_boundary,
        passed=all((
            owner_boundary,
            localhost_boundary,
            zero_cost_boundary,
            durable_queue,
            recovery_boundary,
        )),
    )
