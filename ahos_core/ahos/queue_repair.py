"""Reopen blocked missions that were blocked by *queue state*, not by work.

Two failure classes show up in the real journal:

* ``görev başka işçide veya kapalı`` — the row was left behind a stale lock or a
  dead lease, so nobody could ever claim it again;
* a leftover ``runtime/tasks/<mission_id>.json`` work item from the failed
  attempt, which makes a retry resume mid-way instead of starting clean.

``reopen_blocked`` re-queues such missions under a *fresh* id (history is kept,
nothing is deleted from ``missions``) and moves the stale work item aside.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from .autonomous_company import PersistentMissionQueue, QueueStatus


LOCK_HINTS = (
    "başka işçide veya kapalı",
    "sahiplenilemedi",
    "lease",
    "kuyruk kilidi",
)

#: Yama hedefi birden fazla yerde bulundu → daha uzun bağlamla yeniden denenebilir.
AMBIGUOUS_HINTS = (
    "kez bulundu",
    "satırlar:",
)


def _is_lock_blocked(error: str, include_ambiguous: bool = False) -> bool:
    lowered = (error or "").lower()
    hints = LOCK_HINTS + (AMBIGUOUS_HINTS if include_ambiguous else ())
    return any(hint.lower() in lowered for hint in hints)


def _base_id(mission_id: str) -> str:
    return re.sub(r"-r\d+$", "", mission_id)


def _next_id(
    queue: PersistentMissionQueue,
    base_id: str,
    reserved: set[str] | None = None,
) -> str:
    """Next free ``-rN`` id for this base, skipping ids reserved in this run."""

    taken = reserved if reserved is not None else set()
    suffix = 2
    while queue.get(f"{base_id}-r{suffix}") is not None or f"{base_id}-r{suffix}" in taken:
        suffix += 1
    return f"{base_id}-r{suffix}"


def _stale_dir(runtime_dir: Path) -> Path:
    return Path(runtime_dir) / "tasks" / "_stale"


def reopen_blocked(
    runtime_dir: str | Path,
    *,
    limit: int | None = None,
    dry_run: bool = False,
    max_attempts: int = 2,
    include_ambiguous: bool = False,
) -> dict[str, object]:
    runtime = Path(runtime_dir)
    queue = PersistentMissionQueue(runtime / "company-service.db")
    planned: list[dict[str, str]] = []
    moved: list[str] = []
    reserved: set[str] = set()

    blocked = [
        mission
        for mission in queue.list()
        if mission.status is QueueStatus.BLOCKED
        and _is_lock_blocked(
            getattr(mission, "last_error", "") or "", include_ambiguous
        )
    ]
    blocked.sort(key=lambda mission: str(mission.mission_id))
    if limit is not None:
        blocked = blocked[:limit]

    for mission in blocked:
        base = _base_id(mission.mission_id)
        new_id = _next_id(queue, base, reserved)
        reserved.add(new_id)
        task_file = runtime / "tasks" / f"{base}.json"
        planned.append(
            {
                "old": mission.mission_id,
                "new": new_id,
                "department": mission.primary_department,
                "objective": mission.objective,
                "stale_item": str(task_file) if task_file.exists() else "",
            }
        )
        if dry_run:
            continue

        queue.enqueue(
            mission_id=new_id,
            objective=mission.objective,
            primary_department=mission.primary_department,
            max_attempts=max_attempts,
            replace_existing=False,
        )
        if task_file.exists():
            target = _stale_dir(runtime)
            target.mkdir(parents=True, exist_ok=True)
            shutil.move(str(task_file), str(target / task_file.name))
            moved.append(task_file.name)

    if not dry_run and planned:
        try:
            from .audit import AuditLog

            AuditLog(runtime / "audit.jsonl").append(
                "queue.reopened",
                {
                    "count": len(planned),
                    "missions": [row["new"] for row in planned],
                    "stale_items_moved": moved,
                },
                correlation_id="queue-repair",
            )
        except Exception:  # pragma: no cover - audit must never break repair
            pass

    return {
        "dry_run": dry_run,
        "candidates": len(planned),
        "planned": planned,
        "moved_items": moved,
    }
