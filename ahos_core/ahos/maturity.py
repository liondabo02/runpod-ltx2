from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class CapabilityState(str, Enum):
    MISSING = "missing"
    PARTIAL = "partial"
    IMPLEMENTED = "implemented"
    PROVEN = "proven"


_STATE_FACTOR = {
    CapabilityState.MISSING: 0.0,
    CapabilityState.PARTIAL: 0.5,
    CapabilityState.IMPLEMENTED: 0.8,
    CapabilityState.PROVEN: 1.0,
}


@dataclass(frozen=True, slots=True)
class CapabilityEvidence:
    name: str
    weight: int
    state: CapabilityState
    evidence: str = ""

    def __post_init__(self) -> None:
        if self.weight <= 0:
            raise ValueError("weight must be positive")
        object.__setattr__(self, "state", CapabilityState(self.state))


@dataclass(frozen=True, slots=True)
class MaturityReport:
    score: float
    raw_score: float
    blockers: tuple[str, ...]
    capabilities: tuple[CapabilityEvidence, ...]


CRITICAL_PROOF_GATES = frozenset({
    "deployment_proof",
    "autonomous_runtime_proof",
    "recovery_proof",
})


def evaluate_maturity(capabilities: Iterable[CapabilityEvidence]) -> MaturityReport:
    rows = tuple(capabilities)
    if not rows:
        return MaturityReport(0.0, 0.0, ("no_capabilities",), ())
    total_weight = sum(row.weight for row in rows)
    raw = 100.0 * sum(
        row.weight * _STATE_FACTOR[row.state] for row in rows
    ) / total_weight
    by_name = {row.name: row for row in rows}
    blockers = tuple(sorted(
        gate for gate in CRITICAL_PROOF_GATES
        if gate not in by_name or by_name[gate].state is not CapabilityState.PROVEN
    ))
    ceiling = 95.0 if blockers else 100.0
    score = min(raw, ceiling)
    return MaturityReport(round(score, 2), round(raw, 2), blockers, rows)
