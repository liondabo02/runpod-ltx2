"""Departman bazli duygu/durum ozeti (gercek kuyruk verisinden)."""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "ahos_core"
RUNTIME = CORE / "runtime"
CFG = CORE / "config"


def dept_counts() -> dict:
    db = RUNTIME / "company-service.db"
    out: dict = {}
    if not db.exists():
        return out
    with sqlite3.connect(db) as con:
        rows = con.execute(
            "select primary_department, status, count(*) from missions group by 1,2"
        ).fetchall()
    for dep, status, count in rows:
        out.setdefault(str(dep or "genel"), {})[status] = count
    return out


def main() -> int:
    book = json.loads((CFG / "departments.json").read_text(encoding="utf-8"))
    deps = book.get("departments") if isinstance(book, dict) else book
    counts = dept_counts()
    result = {}
    for dep in deps:
        dep_id = str(dep.get("department_id") or "")
        c = counts.get(dep_id, {})
        completed, blocked, pending = c.get("completed", 0), c.get("blocked", 0), c.get("pending", 0)
        total = max(1, completed + blocked + pending)
        stress = round(min(1.0, blocked / total * 2.0), 3)
        focus = round(max(0.1, 1.0 - stress * 0.7), 3)
        label = "baskı altında" if stress >= 0.6 else ("yük altında" if pending > 30 else "dengeli")
        result[dep_id] = {
            "workers": len(dep.get("workers") or []),
            "completed": completed, "blocked": blocked, "pending": pending,
            "stress": stress, "focus": focus, "label": label,
        }
    payload = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "departments": result}
    (CFG / "department-mood.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"departman: {len(result)} · en stresli: " +
          ", ".join(f"{k}={v['label']}" for k, v in sorted(result.items(), key=lambda kv: -kv[1]["stress"])[:3]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())