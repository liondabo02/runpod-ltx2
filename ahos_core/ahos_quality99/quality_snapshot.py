from __future__ import annotations

from dataclasses import dataclass

from .baseline_profile import phase3_current


@dataclass(frozen=True, slots=True)
class QualitySnapshot:
    score: float
    target: float
    target_reached: bool
    high_risk_open: tuple[str, ...]
    blockers: tuple[str, ...]


def current_snapshot() -> QualitySnapshot:
    report = phase3_current()
    blockers = (
        "windows_coding_queue_lock_race",
        "real_codex_deepseek_separation",
        "real_product_acceptance",
        "android_device_e2e",
        "production_authorization_not_requested",
        "performance_metrics_not_integrated_into_assignment",
    )
    return QualitySnapshot(
        score=report.score,
        target=99.0,
        target_reached=False,
        high_risk_open=report.high_risk_open,
        blockers=blockers,
    )
