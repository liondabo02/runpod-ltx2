from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True, slots=True)
class DashboardConsistencyReport:
    consistent: bool
    blockers: tuple[str, ...]


class DashboardConsistencyAuditor:
    """Compare read models only; never mutate dashboard or runtime state."""

    def evaluate(
        self,
        *,
        queue_status: Mapping[str, object],
        dashboard_coding: Mapping[str, object],
    ) -> DashboardConsistencyReport:
        blockers: list[str] = []
        queue_counts = queue_status.get("counts")
        dash_counts = dashboard_coding.get("counts")
        if not isinstance(queue_counts, Mapping):
            blockers.append("queue_counts_invalid")
        if not isinstance(dash_counts, Mapping):
            blockers.append("dashboard_counts_invalid")
        if isinstance(queue_counts, Mapping) and isinstance(dash_counts, Mapping):
            keys = set(queue_counts) | set(dash_counts)
            for key in sorted(keys):
                if int(queue_counts.get(key, 0)) != int(dash_counts.get(key, 0)):
                    blockers.append(f"count_mismatch:{key}")

        def ids(value: object) -> set[str]:
            if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
                return set()
            return {
                str(row.get("task_id"))
                for row in value
                if isinstance(row, Mapping) and row.get("task_id")
            }

        queue_ids = ids(queue_status.get("tasks"))
        dash_ids = ids(dashboard_coding.get("tasks"))
        if queue_ids != dash_ids:
            missing = sorted(queue_ids - dash_ids)
            extra = sorted(dash_ids - queue_ids)
            if missing:
                blockers.append("dashboard_missing:" + ",".join(missing))
            if extra:
                blockers.append("dashboard_extra:" + ",".join(extra))

        return DashboardConsistencyReport(
            consistent=not blockers,
            blockers=tuple(blockers),
        )
