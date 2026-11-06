"""One shared task record for every consumer.

The office, the CEO, the daemon and any external worker read the same file:

``runtime/tasks/<mission_id>.json``

Fields: objective, department, worker, status, output files, blocker, attempt
and timestamps. Files are rewritten atomically; history stays in the queue and
in the ledgers.
"""

from __future__ import annotations

import json
import re
import sqlite3
import sys
import time
from pathlib import Path

FIELD_ORDER = (
    "mission_id",
    "objective",
    "department",
    "worker",
    "status",
    "output",
    "blocker",
    "attempts",
    "created_at",
    "updated_at",
)


def _dir(runtime_dir: str | Path) -> Path:
    return Path(runtime_dir) / "tasks"


def _path(runtime_dir: str | Path, mission_id: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", mission_id)[:120] or "task"
    return _dir(runtime_dir) / f"{safe}.json"


def update(
    runtime_dir: str | Path,
    mission_id: str,
    *,
    objective: str = "",
    department: str = "",
    worker: str = "",
    status: str = "",
    output: str = "",
    blocker: str = "",
    attempts: int | None = None,
) -> Path:
    path = _path(runtime_dir, mission_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {"created_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    payload["mission_id"] = mission_id
    for key, value in {
        "objective": objective,
        "department": department,
        "worker": worker,
        "status": status,
        "output": output,
        "blocker": blocker,
    }.items():
        if value:
            payload[key] = value[:400]
    if attempts is not None:
        payload["attempts"] = int(attempts)
    payload.setdefault("attempts", 0)
    payload["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
    return path


def get(runtime_dir: str | Path, mission_id: str) -> dict | None:
    try:
        return json.loads(_path(runtime_dir, mission_id).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def list_tasks(runtime_dir: str | Path, limit: int = 20) -> list[dict]:
    folder = _dir(runtime_dir)
    if not folder.is_dir():
        return []
    rows: list[dict] = []
    for path in folder.glob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    rows.sort(key=lambda row: str(row.get("updated_at") or ""), reverse=True)
    return rows[:limit]


def sync_from_queue(runtime_dir: str | Path, limit: int = 40) -> int:
    """Mirror the latest queue rows into task files (idempotent)."""

    runtime = Path(runtime_dir)
    db = runtime / "company-service.db"
    if not db.is_file():
        return 0
    try:
        con = sqlite3.connect(str(db))
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "select mission_id, objective, primary_department, status, updated_at, result_json "
            "from missions order by rowid desc limit ?",
            (limit,),
        ).fetchall()
        con.close()
    except sqlite3.Error:
        return 0
    written = 0
    for row in rows:
        try:
            payload = json.loads(row["result_json"] or "{}")
        except json.JSONDecodeError:
            payload = {}
        steps = payload.get("steps") or []
        summary = " ".join(str(step.get("worker_summary") or "") for step in steps)
        worker = ""
        for step in steps:
            if step.get("worker_id"):
                worker = str(step["worker_id"])
        match = re.search(r"(\d+) dosya değişti", summary)
        changed = int(match.group(1)) if match else 0
        status = str(row["status"])
        blocker = ""
        if status in {"blocked", "failed"}:
            for step in steps:
                text = str(step.get("worker_summary") or "")
                if "başarısız" in text or "engel" in text or "doldu" in text:
                    blocker = text[:300]
                    break
        update(
            runtime,
            str(row["mission_id"]),
            objective=str(row["objective"]),
            department=str(row["primary_department"] or ""),
            worker=worker,
            status=status,
            output=f"{changed} dosya" if changed else "",
            blocker=blocker,
        )
        written += 1
    return written


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # pragma: no cover
        pass
    args = list(sys.argv[1:] if argv is None else argv)
    runtime = Path("runtime")
    if "--runtime-dir" in args:
        position = args.index("--runtime-dir")
        runtime = Path(args[position + 1])
    if "--sync" in args:
        print(f"eşitlendi: {sync_from_queue(runtime)} görev")
    for row in list_tasks(runtime, limit=10):
        print(
            f"{str(row.get('updated_at') or '')[11:19]} {row.get('status','?'):9} "
            f"{str(row.get('worker') or '-'):24} {str(row.get('objective') or '')[:52]} "
            f"{row.get('output') or ''} {('ENGEL: ' + str(row.get('blocker'))[:40]) if row.get('blocker') else ''}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
