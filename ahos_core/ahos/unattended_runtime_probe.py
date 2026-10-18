from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Mapping


def _ts(value: object) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class RuntimeProbeReport:
    passed: bool
    observed_seconds: float
    samples: int
    recoveries: int
    blockers: tuple[str, ...]


class UnattendedRuntimeProbe:
    """Verify a heartbeat timeline as evidence of unattended operation."""

    HEALTHY_STATES = frozenset({"starting", "polling", "idle", "processed"})
    ERROR_STATES = frozenset({"error"})

    def __init__(
        self,
        *,
        minimum_observed_seconds: float = 3600.0,
        maximum_heartbeat_gap_seconds: float = 60.0,
        minimum_samples: int = 10,
    ) -> None:
        if minimum_observed_seconds <= 0 or maximum_heartbeat_gap_seconds <= 0:
            raise ValueError("time limits must be positive")
        if minimum_samples < 2:
            raise ValueError("minimum_samples must be at least 2")
        self.minimum_observed_seconds = float(minimum_observed_seconds)
        self.maximum_heartbeat_gap_seconds = float(maximum_heartbeat_gap_seconds)
        self.minimum_samples = int(minimum_samples)

    def evaluate(self, rows: Iterable[Mapping[str, object]]) -> RuntimeProbeReport:
        parsed: list[tuple[datetime, str]] = []
        blockers: list[str] = []
        for row in rows:
            try:
                parsed.append((_ts(row["timestamp"]), str(row["state"])))
            except (KeyError, TypeError, ValueError):
                blockers.append("invalid_heartbeat_row")
        parsed.sort(key=lambda item: item[0])

        if len(parsed) < self.minimum_samples:
            blockers.append("insufficient_samples")
        if len(parsed) < 2:
            return RuntimeProbeReport(False, 0.0, len(parsed), 0, tuple(sorted(set(blockers))))

        observed = max(0.0, (parsed[-1][0] - parsed[0][0]).total_seconds())
        if observed < self.minimum_observed_seconds:
            blockers.append("observation_window_too_short")

        recoveries = 0
        previous_state: str | None = None
        for (left_time, _), (right_time, right_state) in zip(parsed, parsed[1:]):
            gap = (right_time - left_time).total_seconds()
            if gap > self.maximum_heartbeat_gap_seconds:
                blockers.append("heartbeat_gap_exceeded")
            if gap < 0:
                blockers.append("heartbeat_out_of_order")
            if previous_state in self.ERROR_STATES and right_state in self.HEALTHY_STATES:
                recoveries += 1
            previous_state = right_state

        unknown = sorted({state for _, state in parsed if state not in self.HEALTHY_STATES | self.ERROR_STATES | {"stopped"}})
        if unknown:
            blockers.append("unknown_runtime_state")
        if parsed[-1][1] in {"error", "stopped"}:
            blockers.append("runtime_not_healthy_at_end")

        return RuntimeProbeReport(
            passed=not blockers,
            observed_seconds=round(observed, 3),
            samples=len(parsed),
            recoveries=recoveries,
            blockers=tuple(sorted(set(blockers))),
        )
