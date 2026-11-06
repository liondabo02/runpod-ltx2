"""Live activity registry + bounded, persistent event journal.

The office view needs to show what agents are doing even when tasks finish in a
few hundred milliseconds. We therefore keep an in-memory registry for "right
now" and a bounded journal (last 200 events) persisted to disk for history.
"""

from __future__ import annotations

import hashlib
import json
import threading
from collections import deque
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

MAX_EVENTS = 200
KINDS = ("started", "step_started", "step_finished", "completed", "failed")

_LOCK = threading.RLock()
_ACTIVE: dict[str, dict[str, object]] = {}
_EVENTS: deque[dict[str, object]] = deque(maxlen=MAX_EVENTS)
_SEEN: set[str] = set()
_JOURNAL: Path | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _event_id(kind: str, mission_id: str, worker_id: str, step_id: str, at: str) -> str:
    raw = f"{kind}|{mission_id}|{worker_id}|{step_id}|{at}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def configure(path: str | Path | None) -> None:
    """Attach a journal file and load the most recent events from it."""

    global _JOURNAL
    with _LOCK:
        _JOURNAL = Path(path) if path is not None else None
        if _JOURNAL is None or not _JOURNAL.exists():
            return
        if _EVENTS:
            return
        for line in _JOURNAL.read_text(encoding="utf-8", errors="ignore").splitlines():
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict) and event.get("id") not in _SEEN:
                _EVENTS.append(event)
                _SEEN.add(str(event.get("id")))


def _emit(kind: str, **fields: object) -> dict[str, object] | None:
    if kind not in KINDS:
        raise ValueError(f"unknown event kind: {kind}")
    at = _now()
    event = {
        "id": _event_id(
            kind,
            str(fields.get("mission_id") or ""),
            str(fields.get("worker_id") or ""),
            str(fields.get("step_id") or ""),
            at,
        ),
        "kind": kind,
        "at": at,
        **fields,
    }
    with _LOCK:
        if event["id"] in _SEEN:
            return None
        _SEEN.add(str(event["id"]))
        _EVENTS.append(event)
        if _JOURNAL is not None:
            _JOURNAL.parent.mkdir(parents=True, exist_ok=True)
            with _JOURNAL.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, ensure_ascii=False) + "\n")
            lines = _JOURNAL.read_text(encoding="utf-8", errors="ignore").splitlines()
            if len(lines) > MAX_EVENTS * 2:
                keep = lines[-MAX_EVENTS:]
                _JOURNAL.write_text("\n".join(keep) + "\n", encoding="utf-8")
    return event


def mission_started(mission_id: str, department: str, objective: str) -> None:
    _emit("started", mission_id=mission_id, department=department, objective=objective[:160])


def mission_finished(mission_id: str, department: str, status: str, reason: str = "") -> None:
    _emit(
        "completed" if status == "completed" else "failed",
        mission_id=mission_id,
        department=department,
        status=status,
        reason=reason[:200],
    )


@contextmanager
def track(
    worker_id: str,
    mission_id: str,
    step_id: str,
    department: str,
) -> Iterator[None]:
    started_at = _now()
    _emit(
        "step_started",
        mission_id=mission_id,
        worker_id=worker_id,
        step_id=step_id,
        department=department,
    )
    with _LOCK:
        _ACTIVE[worker_id] = {
            "mission_id": mission_id,
            "step_id": step_id,
            "department": department,
            "started_at": started_at,
        }
    try:
        yield
    finally:
        with _LOCK:
            _ACTIVE.pop(worker_id, None)
        _emit(
            "step_finished",
            mission_id=mission_id,
            worker_id=worker_id,
            step_id=step_id,
            department=department,
        )


def active() -> dict[str, dict[str, object]]:
    with _LOCK:
        return {key: dict(value) for key, value in _ACTIVE.items()}


def drop_mission(mission_id: str) -> int:
    """Forget in-flight workers of a mission (used when a mission times out).

    A timed-out executor thread may keep running in the background; its worker
    registrations must not keep the office view showing them as "working".
    """

    with _LOCK:
        stale = [
            worker_id
            for worker_id, entry in _ACTIVE.items()
            if entry.get("mission_id") == mission_id
        ]
        for worker_id in stale:
            _ACTIVE.pop(worker_id, None)
        return len(stale)


def history(limit: int = 50) -> list[dict[str, object]]:
    with _LOCK:
        return [dict(event) for event in list(_EVENTS)[-limit:]]


def reset_for_tests() -> None:
    with _LOCK:
        _ACTIVE.clear()
        _EVENTS.clear()
        _SEEN.clear()
        global _JOURNAL
        _JOURNAL = None
