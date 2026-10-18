from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True, slots=True)
class WatchdogDecision:
    action: str
    reason: str


class Watchdog:
    def decide(self, *, heartbeat_at: datetime, now: datetime | None = None, max_age_seconds: float = 60.0) -> WatchdogDecision:
        if heartbeat_at.tzinfo is None:
            raise ValueError("heartbeat must be timezone-aware")
        current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        age = max(0.0, (current - heartbeat_at.astimezone(timezone.utc)).total_seconds())
        if age > max_age_seconds:
            return WatchdogDecision("restart_candidate", f"stale_heartbeat:{age:.3f}")
        return WatchdogDecision("none", "healthy")
