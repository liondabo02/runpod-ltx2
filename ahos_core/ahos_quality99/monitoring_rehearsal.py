from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from ahos.error_budget import ErrorBudget
from ahos.watchdog import Watchdog


@dataclass(frozen=True, slots=True)
class MonitoringRehearsalReport:
    stale_heartbeat_detected: bool
    error_budget_breach_detected: bool
    healthy_heartbeat_accepted: bool
    passed: bool


def run_monitoring_rehearsal() -> MonitoringRehearsalReport:
    now = datetime.now(timezone.utc)
    watchdog = Watchdog()
    stale = watchdog.decide(
        heartbeat_at=now - timedelta(seconds=121),
        now=now,
        max_age_seconds=60,
    )
    healthy = watchdog.decide(
        heartbeat_at=now - timedelta(seconds=5),
        now=now,
        max_age_seconds=60,
    )
    budget = ErrorBudget().evaluate(successful=95, total=100, target=0.99)

    stale_ok = stale.action == "restart_candidate"
    healthy_ok = healthy.action == "none"
    budget_ok = budget.breached is True
    return MonitoringRehearsalReport(
        stale_heartbeat_detected=stale_ok,
        error_budget_breach_detected=budget_ok,
        healthy_heartbeat_accepted=healthy_ok,
        passed=stale_ok and budget_ok and healthy_ok,
    )
