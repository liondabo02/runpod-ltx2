from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Iterable


@dataclass(frozen=True, slots=True)
class WorkerOutcome:
    worker_id: str
    succeeded: bool
    qa_passed: bool
    latency_seconds: float
    retry_count: int = 0

    def __post_init__(self) -> None:
        if not self.worker_id:
            raise ValueError("worker_id required")
        if self.latency_seconds < 0 or self.retry_count < 0:
            raise ValueError("latency/retry must be nonnegative")


@dataclass(frozen=True, slots=True)
class WorkerScore:
    worker_id: str
    score: float
    samples: int
    success_rate: float
    qa_rate: float
    average_latency: float
    average_retries: float


class WorkerPerformanceModel:
    """Evidence-only ranking; does not assign or execute work by itself."""

    def rank(self, outcomes: Iterable[WorkerOutcome]) -> tuple[WorkerScore, ...]:
        grouped: dict[str, list[WorkerOutcome]] = {}
        for row in outcomes:
            grouped.setdefault(row.worker_id, []).append(row)
        scores: list[WorkerScore] = []
        for worker_id, rows in grouped.items():
            success = sum(r.succeeded for r in rows) / len(rows)
            qa = sum(r.qa_passed for r in rows) / len(rows)
            latency = mean(r.latency_seconds for r in rows)
            retries = mean(r.retry_count for r in rows)
            latency_factor = 1.0 / (1.0 + latency / 300.0)
            retry_factor = 1.0 / (1.0 + retries)
            score = 100.0 * (
                0.45 * success
                + 0.35 * qa
                + 0.10 * latency_factor
                + 0.10 * retry_factor
            )
            scores.append(WorkerScore(
                worker_id=worker_id,
                score=round(score, 3),
                samples=len(rows),
                success_rate=success,
                qa_rate=qa,
                average_latency=latency,
                average_retries=retries,
            ))
        return tuple(sorted(scores, key=lambda row: (-row.score, row.worker_id)))
