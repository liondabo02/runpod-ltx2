from __future__ import annotations

from dataclasses import dataclass

from .queue_stress import run_synthetic_queue_stress
from .process_recovery_e2e import run_process_recovery_e2e


@dataclass(frozen=True, slots=True)
class SoakReport:
    queue_rounds: int
    queue_tasks_total: int
    queue_failures: int
    recovery_rounds: int
    recovery_failures: int
    passed: bool


def run_bounded_soak(*, queue_rounds: int = 10, tasks_per_round: int = 100,
                     recovery_rounds: int = 5) -> SoakReport:
    """Bounded local-only soak; no external provider or production state."""
    if not 1 <= queue_rounds <= 50:
        raise ValueError("queue_rounds must be in [1,50]")
    if not 1 <= tasks_per_round <= 1000:
        raise ValueError("tasks_per_round must be in [1,1000]")
    if not 1 <= recovery_rounds <= 20:
        raise ValueError("recovery_rounds must be in [1,20]")

    queue_failures = 0
    for _ in range(queue_rounds):
        if not run_synthetic_queue_stress(task_count=tasks_per_round).passed:
            queue_failures += 1

    recovery_failures = 0
    for _ in range(recovery_rounds):
        if not run_process_recovery_e2e().passed:
            recovery_failures += 1

    return SoakReport(
        queue_rounds=queue_rounds,
        queue_tasks_total=queue_rounds * tasks_per_round,
        queue_failures=queue_failures,
        recovery_rounds=recovery_rounds,
        recovery_failures=recovery_failures,
        passed=queue_failures == 0 and recovery_failures == 0,
    )
