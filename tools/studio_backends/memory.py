"""Append-only studio memory: one JSONL log per worker + a compact digest.

This is the studio-level learning substrate: every run records status, metrics and
lessons. `digest()` gives the next run its own history (pass rate + recent
lessons) so workers adapt instead of repeating mistakes. Advisory only.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MEMORY = ROOT / "studio" / "agents" / "memory"


def remember(worker_id, record, limit=500):
    MEMORY.mkdir(parents=True, exist_ok=True)
    path = MEMORY / ("%s.jsonl" % worker_id)
    entry = dict(record)
    entry["worker_id"] = worker_id
    entry["at"] = datetime.now(timezone.utc).isoformat()
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) > limit:
        path.write_text("\n".join(lines[-limit:]) + "\n", encoding="utf-8")
    return path


def digest(worker_id, window=20):
    path = MEMORY / ("%s.jsonl" % worker_id)
    if not path.is_file():
        return {"runs": 0, "pass_rate": None, "lessons": [], "last_status": None}
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines()[-window:]:
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    if not rows:
        return {"runs": 0, "pass_rate": None, "lessons": [], "last_status": None}
    passes = sum(1 for row in rows if row.get("status") == "PASSED")
    lessons = []
    for row in rows:
        for lesson in row.get("lessons") or []:
            if lesson not in lessons:
                lessons.append(lesson)
    return {"runs": len(rows),
            "pass_rate": round(passes / float(len(rows)), 3),
            "lessons": lessons[-10:],
            "last_status": rows[-1].get("status")}
