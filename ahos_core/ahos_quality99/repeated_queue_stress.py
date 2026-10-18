from __future__ import annotations

from dataclasses import dataclass

from .concurrent_queue_stress import run_concurrent_queue_stress


@dataclass(frozen=True, slots=True)
class RepeatedStressReport:
    rounds: int
    passed_rounds: int
    failed_rounds: int
    duplicate_claims: int
    lost_records: int
    errors: tuple[str, ...]
    passed: bool


def run_repeated_queue_stress(*, rounds: int = 5, task_count: int = 100, workers: int = 4) -> RepeatedStressReport:
    if not 1 <= rounds <= 50:
        raise ValueError("rounds must be in [1,50]")
    passed_rounds = 0
    duplicates = 0
    lost = 0
    errors: list[str] = []
    for _ in range(rounds):
        report = run_concurrent_queue_stress(task_count=task_count, workers=workers)
        passed_rounds += int(report.passed)
        duplicates += report.duplicates
        lost += report.lost
        errors.extend(report.errors)
    failed = rounds - passed_rounds
    return RepeatedStressReport(
        rounds=rounds,
        passed_rounds=passed_rounds,
        failed_rounds=failed,
        duplicate_claims=duplicates,
        lost_records=lost,
        errors=tuple(sorted(errors)),
        passed=failed == 0 and duplicates == 0 and lost == 0 and not errors,
    )
