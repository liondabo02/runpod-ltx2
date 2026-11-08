"""Worker quality metrics.

Every real worker call is recorded with its outcome so the holding can show
per-agent quality (runs, successes, failures, average duration, last error)
instead of inventing performance numbers.
"""

from __future__ import annotations

import json
import math
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

MAX_LINES = 2000
_LOCK = threading.RLock()
_RUNTIME_DIR: Path | None = None


def configure(runtime_dir: str | Path | None) -> None:
    global _RUNTIME_DIR
    _RUNTIME_DIR = Path(runtime_dir) if runtime_dir is not None else None


def current_dir() -> Path | None:
    return _RUNTIME_DIR


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _path(runtime_dir: str | Path) -> Path:
    return Path(runtime_dir) / "worker-metrics.jsonl"


def record(
    runtime_dir: str | Path,
    *,
    worker_id: str,
    mission_id: str,
    step_id: str,
    department: str,
    success: bool,
    duration_ms: float,
    reason: str = "",
) -> None:
    path = _path(runtime_dir)
    entry = {
        "at": _now(),
        "worker_id": worker_id,
        "mission_id": mission_id,
        "step_id": step_id,
        "department": department,
        "success": bool(success),
        "duration_ms": round(float(duration_ms), 1),
        "reason": (reason or "")[:200],
    }
    with _LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        if len(lines) > MAX_LINES * 2:
            path.write_text("\n".join(lines[-MAX_LINES:]) + "\n", encoding="utf-8")


def _entries(runtime_dir: str | Path) -> list[dict[str, object]]:
    path = _path(runtime_dir)
    if not path.exists():
        return []
    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict) or not isinstance(row.get('success'), bool):
            continue
        try:
            duration = float(row.get('duration_ms') or 0)
        except (ValueError, TypeError):
            continue
        if not math.isfinite(duration) or duration < 0:
            continue
        rows.append(row)
    return rows


def selection_score(row: dict[str, object]) -> float:
    """Smoothed Wilson lower bound, not a claim of future competence.

    Two prior observations keep an untried worker eligible; larger successful
    samples beat one lucky run. Costs/capabilities/availability remain hard gates.
    """
    try:
        runs = max(0, int(row.get('runs') or 0))
        successes = min(runs, max(0, int(row.get('successes') or 0)))
    except (ValueError, TypeError, OverflowError):
        runs, successes = 0, 0
    n, p, z = runs + 2, (successes + 1) / (runs + 2), 1.96
    return (p + z*z/(2*n) - z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))) / (1 + z*z/n)


def summary(runtime_dir: str | Path) -> dict[str, dict[str, object]]:
    """Per-worker quality summary computed from real recorded calls."""

    result: dict[str, dict[str, object]] = {}
    for row in _entries(runtime_dir):
        worker = str(row.get("worker_id") or "")
        if not worker:
            continue
        item = result.setdefault(
            worker,
            {
                "runs": 0,
                "successes": 0,
                "failures": 0,
                "total_ms": 0.0,
                "last_error": "",
                "last_at": "",
                "department": row.get("department") or "",
                "reassignments": 0,
            },
        )
        item["runs"] = int(item["runs"]) + 1
        if str(row.get("reason") or "").startswith("yeniden atama"):
            item["reassignments"] = int(item["reassignments"]) + 1
        if row.get("success"):
            item["successes"] = int(item["successes"]) + 1
        else:
            item["failures"] = int(item["failures"]) + 1
            item["last_error"] = str(row.get("reason") or "")[:120]
        item["total_ms"] = float(item["total_ms"]) + float(row.get("duration_ms") or 0.0)
        item["last_at"] = str(row.get("at") or "")

    for item in result.values():
        runs = max(1, int(item["runs"]))
        item["avg_ms"] = round(float(item["total_ms"]) / runs, 1)
        item["success_rate"] = round(int(item["successes"]) / runs, 3)
    return result


def recent_failures(runtime_dir: str | Path, limit: int = 5) -> list[dict[str, object]]:
    rows = [row for row in _entries(runtime_dir) if not row.get("success")]
    return rows[-limit:]


def reset_for_tests(runtime_dir: str | Path) -> None:
    path = _path(runtime_dir)
    if path.exists():
        path.unlink()


def timed() -> float:
    return time.monotonic()


def record_here(
    *,
    worker_id: str,
    mission_id: str,
    step_id: str,
    department: str,
    success: bool,
    duration_ms: float,
    reason: str = "",
) -> None:
    """Record into the configured runtime dir (no-op when not configured)."""

    target = _RUNTIME_DIR
    if target is None:
        return
    record(
        target,
        worker_id=worker_id,
        mission_id=mission_id,
        step_id=step_id,
        department=department,
        success=success,
        duration_ms=duration_ms,
        reason=reason,
    )
