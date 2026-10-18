from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class MeasurementState(str, Enum):
    PROVEN = "proven"
    PARTIAL = "partial"
    UNMEASURED = "unmeasured"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class QualityArea:
    area_id: str
    name: str
    state: MeasurementState
    weight: int
    evidence: str
    gap: str
    success_criterion: str

    def __post_init__(self) -> None:
        if not self.area_id or not self.name:
            raise ValueError("area_id and name are required")
        if not 1 <= self.weight <= 100:
            raise ValueError("weight must be in [1,100]")


_FACTOR = {
    MeasurementState.PROVEN: 1.0,
    MeasurementState.PARTIAL: 0.6,
    MeasurementState.UNMEASURED: 0.0,
    MeasurementState.BLOCKED: 0.0,
}


@dataclass(frozen=True, slots=True)
class QualityMatrixReport:
    score: float
    areas: tuple[QualityArea, ...]
    high_risk_open: tuple[str, ...]
    target_reached: bool


def evaluate_quality(
    areas: Iterable[QualityArea],
    *,
    target: float = 99.0,
    high_risk_area_ids: frozenset[str] = frozenset({
        "worker_execution",
        "recovery",
        "concurrency",
        "data_integrity",
        "security",
        "real_product",
    }),
) -> QualityMatrixReport:
    rows = tuple(areas)
    if not rows:
        raise ValueError("at least one area is required")
    total = sum(row.weight for row in rows)
    score = 100.0 * sum(row.weight * _FACTOR[row.state] for row in rows) / total
    high_risk_open = tuple(sorted(
        row.area_id
        for row in rows
        if row.area_id in high_risk_area_ids and row.state is not MeasurementState.PROVEN
    ))
    return QualityMatrixReport(
        score=round(score, 2),
        areas=rows,
        high_risk_open=high_risk_open,
        target_reached=score >= target and not high_risk_open
    )
