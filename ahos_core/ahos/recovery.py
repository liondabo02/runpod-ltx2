"""Crash recovery for the durable mission queue.

A process can die between ``claim_next`` and ``complete``. On startup AHOS must
put half-finished work back into a well-defined state instead of losing it or
running it twice:

* expired leases are released by the queue itself,
* missions whose lease expired and whose retries are exhausted are blocked with
  an explicit reason (never silently retried),
* everything else is left claimable for a bounded retry.
"""

from __future__ import annotations

import time
from pathlib import Path

from .autonomous_company import PersistentMissionQueue, QueueStatus
from .mission_orchestrator import MissionResult, MissionStatus


def recover(
    runtime_dir: str | Path,
    queue: PersistentMissionQueue,
    *,
    now: float | None = None,
) -> dict[str, object]:
    moment = time.time() if now is None else now
    recovered = queue.recover_expired_leases(now=moment)

    blocked: list[str] = []
    for mission in queue.list():
        if mission.status not in {QueueStatus.RUNNING, QueueStatus.PENDING}:
            continue
        if (
            mission.status is QueueStatus.RUNNING
            and mission.lease_until is not None
            and mission.lease_until >= moment
        ):
            continue
        if mission.attempts < mission.max_attempts:
            continue
        if mission.status is QueueStatus.PENDING and mission.lease_owner is not None:
            continue
        owner = mission.lease_owner or "recovery"
        reason = (
            "yarım kalan işlem: süreç çöktü ve yeniden deneme "
            f"hakkı kalmadı ({mission.attempts}/{mission.max_attempts})"
        )
        if queue.block_orphan(mission.mission_id, reason=reason):
            blocked.append(mission.mission_id)
        continue

    try:
        from .audit import AuditLog

        AuditLog(Path(runtime_dir) / "audit.jsonl").append(
            "runtime.recovered",
            {
                "expired_leases": recovered,
                "blocked_missions": blocked,
            },
            correlation_id="recovery",
        )
    except Exception:  # pragma: no cover - audit must never break startup
        pass

    return {"expired_leases": recovered, "blocked": blocked}
