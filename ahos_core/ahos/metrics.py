from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

from .mission_store import MissionStatus


@dataclass(frozen=True, slots=True)
class MissionMetric:
    """Local measurements for one mission attempt."""

    status: MissionStatus
    latency_seconds: float
    estimated_cost_usd: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", MissionStatus(self.status))
        object.__setattr__(
            self,
            "latency_seconds",
            _nonnegative_float(self.latency_seconds, "latency_seconds"),
        )
        object.__setattr__(
            self,
            "estimated_cost_usd",
            _nonnegative_float(self.estimated_cost_usd, "estimated_cost_usd"),
        )


@dataclass(frozen=True, slots=True)
class MetricsSnapshot:
    """Immutable aggregate of local mission measurements."""

    total_missions: int
    successful_missions: int
    failed_missions: int
    average_latency_seconds: float
    estimated_cost_usd: float

    def __post_init__(self) -> None:
        for name in (
            "total_missions",
            "successful_missions",
            "failed_missions",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a nonnegative integer")
        if self.successful_missions + self.failed_missions > self.total_missions:
            raise ValueError("successful and failed missions exceed total missions")
        object.__setattr__(
            self,
            "average_latency_seconds",
            _nonnegative_float(
                self.average_latency_seconds, "average_latency_seconds"
            ),
        )
        object.__setattr__(
            self,
            "estimated_cost_usd",
            _nonnegative_float(self.estimated_cost_usd, "estimated_cost_usd"),
        )

    @property
    def success_rate(self) -> float:
        return self.successful_missions / self.total_missions if self.total_missions else 0.0

    @property
    def failure_rate(self) -> float:
        return self.failed_missions / self.total_missions if self.total_missions else 0.0

    @classmethod
    def from_missions(cls, missions: Iterable[MissionMetric]) -> MetricsSnapshot:
        measurements = tuple(missions)
        total = len(measurements)
        successful = sum(
            measurement.status is MissionStatus.COMPLETED for measurement in measurements
        )
        failed = sum(
            measurement.status is MissionStatus.FAILED for measurement in measurements
        )
        latency = (
            sum(measurement.latency_seconds for measurement in measurements) / total
            if total
            else 0.0
        )
        cost = sum(measurement.estimated_cost_usd for measurement in measurements)
        return cls(total, successful, failed, latency, cost)


def report_metrics(snapshot: MetricsSnapshot) -> dict[str, float | int]:
    """Return a serializable local report for a metrics snapshot."""

    return {
        "total_missions": snapshot.total_missions,
        "successful_missions": snapshot.successful_missions,
        "failed_missions": snapshot.failed_missions,
        "success_rate": snapshot.success_rate,
        "failure_rate": snapshot.failure_rate,
        "average_latency_seconds": snapshot.average_latency_seconds,
        "estimated_cost_usd": snapshot.estimated_cost_usd,
    }


def _nonnegative_float(value: float, name: str) -> float:
    try:
        normalized = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must be a finite nonnegative number") from error
    if not math.isfinite(normalized) or normalized < 0:
        raise ValueError(f"{name} must be a finite nonnegative number")
    return normalized
