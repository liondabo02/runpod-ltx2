from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ErrorBudgetReport:
    availability: float
    target: float
    budget_remaining: float
    breached: bool


class ErrorBudget:
    def evaluate(self, *, successful: int, total: int, target: float = 0.99) -> ErrorBudgetReport:
        if total <= 0 or successful < 0 or successful > total:
            raise ValueError("invalid counts")
        if not 0 < target <= 1:
            raise ValueError("target must be in (0,1]")
        availability = successful / total
        allowed_failure = 1 - target
        actual_failure = 1 - availability
        remaining = allowed_failure - actual_failure
        return ErrorBudgetReport(
            availability=availability,
            target=target,
            budget_remaining=remaining,
            breached=remaining < 0,
        )
