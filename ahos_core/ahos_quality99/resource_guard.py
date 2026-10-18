from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ResourceDecision:
    allow_heavy_work: bool
    free_ratio: float
    state: str
    reason: str


class ResourceGuard:
    """Fail-closed resource admission for quality-program heavy work."""

    def __init__(self, *, min_free_ratio: float = 0.10, critical_free_ratio: float = 0.05) -> None:
        if not 0 < critical_free_ratio <= min_free_ratio < 1:
            raise ValueError("invalid free-memory thresholds")
        self.min_free_ratio = min_free_ratio
        self.critical_free_ratio = critical_free_ratio

    def evaluate(self, *, total_memory_kb: int, free_memory_kb: int) -> ResourceDecision:
        if total_memory_kb <= 0 or free_memory_kb < 0 or free_memory_kb > total_memory_kb:
            raise ValueError("invalid memory values")
        ratio = free_memory_kb / total_memory_kb
        if ratio < self.critical_free_ratio:
            return ResourceDecision(False, ratio, "critical", "free_memory_below_critical_threshold")
        if ratio < self.min_free_ratio:
            return ResourceDecision(False, ratio, "degraded", "free_memory_below_heavy_work_threshold")
        return ResourceDecision(True, ratio, "healthy", "resources_available")
