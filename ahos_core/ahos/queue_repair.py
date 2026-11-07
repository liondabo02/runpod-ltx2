"""Reopen blocked missions that were blocked by *queue state*, not by work.

Two failure classes show up in the real journal:

* ``görev başka işçide veya kapalı`` — the row was left behind a stale lock or a
  dead lease, so nobody could ever claim it again;
* a leftover ``runtime/tasks/<mission_id>.json`` work item from the failed
  attempt, which makes a retry resume mid-way instead of starting clean.

A third class is *observable and provably repaired*: the task board was
unreadable when the mission ran (``görev panosu biçimi geçersiz``). Replaying
those is only allowed while the current board still validates, so a corrupt
board can never be replayed into more corruption.

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

#: Görev panosu okunamadığı için engellenen görevler; yalnız panosu sağlamken tekrar denenir.
BOARD_HINTS = (
    "panosu biçimi geçersiz",
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


def _is_board_blocked(error: str) -> bool:
    lowered = (error or "").lower()
    return any(hint.lower() in lowered for hint in BOARD_HINTS)


def board_schema_valid(runtime_dir: str | Path) -> tuple[bool, str]:
    """Pano şu anda okunabiliyor mu? (tekrar deneme ön koşulu)"""

    path = Path(runtime_dir) / "taskboard.json"
    if not path.is_file():
        return False, "taskboard.json yok"
    from .taskboard import TaskBoard, TaskBoardError

    try:
        TaskBoard(path).tasks()
    except TaskBoardError as exc:
        return False, str(exc)
    return True, "ok"


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
    include_board_schema: bool = False,
    match: str = "",
) -> dict[str, object]:
    runtime = Path(runtime_dir)
    if include_board_schema:
        # Fail closed: bozuk pano ile tekrar deneme yeni kayıt üretmez.
        valid, detail = board_schema_valid(runtime)
        if not valid:
            raise ValueError(f"taskboard schema is invalid; repair it first: {detail}")
    queue = PersistentMissionQueue(runtime / "company-service.db")
    planned: list[dict[str, str]] = []
    moved: list[str] = []
    skipped: list[dict[str, str]] = []
    reserved: set[str] = set()
    needle = str(match or "").strip().casefold()

    # A mission that was already recovered once (a completed ``-rN`` sibling)
    # must not be reopened again: replay is idempotent per base id.
    recovered: dict[str, str] = {}
    for mission in queue.list():
        if mission.status is QueueStatus.COMPLETED:
            recovered.setdefault(_base_id(mission.mission_id), mission.mission_id)

    blocked = []
    for mission in queue.list():
        if mission.status is not QueueStatus.BLOCKED:
            continue
        error = getattr(mission, "last_error", "") or ""
        class_name = ""
        if _is_lock_blocked(error, include_ambiguous):
            class_name = "lock"
        elif include_board_schema and _is_board_blocked(error):
            class_name = "board_schema"
        if not class_name:
            continue
        if needle and needle not in f"{mission.mission_id} {mission.objective}".casefold():
            continue
        blocked.append((mission, class_name))
    blocked.sort(key=lambda item: str(item[0].mission_id))
    if limit is not None:
        blocked = blocked[:limit]

    for mission, class_name in blocked:
        base = _base_id(mission.mission_id)
        prior = recovered.get(base)
        if prior:
            skipped.append({"old": mission.mission_id, "class": class_name,
                            "reason": f"already recovered as {prior}"})
            continue
        new_id = _next_id(queue, base, reserved)
        reserved.add(new_id)
        task_file = runtime / "tasks" / f"{base}.json"
        planned.append(
            {
                "old": mission.mission_id,
                "new": new_id,
                "department": mission.primary_department,
                "objective": mission.objective,
                "class": class_name,
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
                    "classes": sorted({row["class"] for row in planned}),
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
        "skipped_recovered": skipped,
    }
