from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True, slots=True)
class ArchitectureAudit:
    passed: bool
    satisfied: tuple[str, ...]
    gaps: tuple[str, ...]


class SystemDesignPrimerAudit:
    """Map public System Design Primer reliability concepts to AHOS evidence."""

    REQUIRED = (
        "persistent_task_queue",
        "idempotency",
        "back_pressure",
        "bounded_concurrency",
        "health_checks",
        "failure_recovery",
        "data_integrity",
        "observability",
        "authority_boundary",
        "deployment_rollback",
    )

    def evaluate(self, evidence: Mapping[str, bool]) -> ArchitectureAudit:
        satisfied = tuple(name for name in self.REQUIRED if evidence.get(name) is True)
        gaps = tuple(name for name in self.REQUIRED if evidence.get(name) is not True)
        return ArchitectureAudit(not gaps, satisfied, gaps)
