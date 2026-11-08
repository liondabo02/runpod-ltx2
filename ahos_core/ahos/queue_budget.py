"""Read-only admission telemetry for bounded mission creation.

SQLite missions is authoritative. A missing/locked database means automatic
sandbox or initiative generation fails closed, not 'pending == 0'.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

try:  # Eski main'de sabit henüz yok; kapasite değeri aynı kalır.
    from .autonomous_company import MAX_PENDING_MISSIONS
except ImportError:  # pragma: no cover - geriye dönük uyum
    MAX_PENDING_MISSIONS = 300

AUTONOMOUS_RESUME_BELOW = 240

def pending_count(runtime_dir: str | Path) -> int | None:
    db = Path(runtime_dir) / "company-service.db"
    if not db.is_file():
        return None
    try:
        with sqlite3.connect("file:" + db.resolve().as_posix() + "?mode=ro",
                             uri=True, timeout=3) as connection:
            return int(connection.execute(
                "SELECT COUNT(*) FROM missions WHERE status='pending'"
            ).fetchone()[0])
    except (sqlite3.Error, OSError, TypeError, ValueError):
        return None


def can_generate(runtime_dir: str | Path, *, headroom: bool = True) -> dict:
    pending = pending_count(runtime_dir)
    limit = AUTONOMOUS_RESUME_BELOW if headroom else MAX_PENDING_MISSIONS
    allowed = pending is not None and pending < limit
    return {
        "allowed": allowed,
        "pending": pending,
        "limit": MAX_PENDING_MISSIONS,
        "resume_below": AUTONOMOUS_RESUME_BELOW,
        "reason": (
            "db_unavailable" if pending is None
            else "backpressure" if not allowed
            else "capacity_available"
        ),
    }
