from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True, slots=True)
class RecoveryRehearsalReport:
    passed: bool
    recovered_tasks: int
    blockers: tuple[str, ...]


class RecoveryRehearsal:
    """Evaluate before/after runtime snapshots without mutating production state."""

    def evaluate(
        self,
        *,
        before: Mapping[str, object],
        after: Mapping[str, object],
    ) -> RecoveryRehearsalReport:
        blockers: list[str] = []
        before_tasks = before.get("tasks")
        after_tasks = after.get("tasks")
        if not isinstance(before_tasks, list) or not isinstance(after_tasks, list):
            return RecoveryRehearsalReport(False, 0, ("invalid_snapshot",))

        after_by_id = {
            str(item.get("task_id")): item
            for item in after_tasks
            if isinstance(item, Mapping) and item.get("task_id")
        }
        recovered = 0
        for item in before_tasks:
            if not isinstance(item, Mapping):
                continue
            task_id = str(item.get("task_id") or "")
            if not task_id or item.get("status") != "running":
                continue
            current = after_by_id.get(task_id)
            if current is None:
                blockers.append(f"{task_id}:missing_after_recovery")
                continue
            if current.get("status") in {
                "queued",
                "waiting_provider",
                "waiting_owner_approval",
                "owner_approved",
                "completed",
                "retries_exhausted",
            }:
                recovered += 1
            else:
                blockers.append(f"{task_id}:still_unrecoverable")

        if before.get("heartbeat_state") == "error" and after.get("heartbeat_state") not in {
            "starting", "polling", "idle", "processed"
        }:
            blockers.append("heartbeat_not_recovered")

        if recovered == 0 and any(
            isinstance(item, Mapping) and item.get("status") == "running"
            for item in before_tasks
        ):
            blockers.append("no_running_task_recovered")

        return RecoveryRehearsalReport(
            passed=not blockers,
            recovered_tasks=recovered,
            blockers=tuple(sorted(set(blockers))),
        )
