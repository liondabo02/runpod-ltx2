"""Task tracking: where did my request go, how far is it, what came out?

The owner types something in the office. That becomes an idea with tasks in one
department. This module joins the idea tasks with the mission queue so the office
can show, per task: department, status, how many files changed and the blocker.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path


def _missions(runtime: Path) -> list[dict]:
    db = runtime / "company-service.db"
    if not db.is_file():
        return []
    try:
        con = sqlite3.connect(str(db))
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "select mission_id, objective, primary_department, status, result_json "
            "from missions order by rowid desc limit 300"
        ).fetchall()
        con.close()
    except sqlite3.Error:
        return []
    import re

    result: list[dict] = []
    for row in rows:
        try:
            payload = json.loads(row["result_json"] or "{}")
        except json.JSONDecodeError:
            payload = {}
        steps = payload.get("steps") or []
        text = " ".join(str(step.get("worker_summary") or "") for step in steps)
        match = re.search(r"(\d+) dosya", text)
        blocker = ""
        if str(row["status"]) in {"blocked", "failed"}:
            blocker = text[:200] or "hiç çalışmadı"
        result.append(
            {
                "mission_id": str(row["mission_id"]),
                "objective": str(row["objective"]),
                "department": str(row["primary_department"] or ""),
                "status": str(row["status"]),
                "changed": int(match.group(1)) if match else 0,
                "blocker": blocker,
            }
        )
    return result


def track(runtime_dir: str | Path, idea_id: str) -> dict | None:
    runtime = Path(runtime_dir)
    path = runtime / "ideas" / f"{idea_id}.json"
    try:
        idea = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    missions = _missions(runtime)
    tasks = []
    done = 0
    for task in idea.get("tasks") or []:
        title = str(task.get("title") or "")
        match = next((m for m in missions if m["objective"] == title), None)
        if match is None:
            match = next((m for m in missions if title and title in m["objective"]), None)
        status = str(task.get("status") or "")
        production = task.get('workflow') == 'studio-production-v1'
        if not production and match is not None and match["status"] == "completed":
            status = "done"
        elif not production and match is not None and match["status"] in {"blocked", "failed"}:
            status = "blocked"
        if status == "done":
            done += 1
        native_artifacts = []
        if production:
            event_path = runtime / 'studio-production' / idea_id / 'events' / f"{task.get('task_id')}-{task.get('attempts',0)}.json"
            try:
                event = json.loads(event_path.read_text(encoding='utf-8'))
                if event.get('success') is True and status == 'done':
                    base = (runtime / 'studio-production' / idea_id).resolve()
                    native_artifacts = [str(Path(p)) for p in event.get('artifacts', []) if Path(p).resolve().is_relative_to(base) and Path(p).is_file()]
            except (OSError, ValueError, TypeError):
                pass
        tasks.append(
            {
                "title": title,
                "status": status,
                "department": idea.get("department_id"),
                "mission_id": match["mission_id"] if match else "",
                "changed": len(native_artifacts) if production else (match["changed"] if match else 0),
                "blocker": str(task.get('blocker') or '') if production else (match["blocker"] if match else ""),
                "worker_id": task.get('worker_id', ''),
                "depends_on": task.get('depends_on', []),
                "language": task.get('language', ''),
                "output": ', '.join(Path(p).name for p in native_artifacts) if production else (f"{match['changed']} dosya" if match and match["changed"] else ""),
                "artifacts": native_artifacts,
            }
        )
    total = len(tasks)
    return {
        "idea_id": idea_id,
        "text": idea.get("text", ""),
        "department": idea.get("department_id", ""),
        "department_name": idea.get("department_name", ""),
        "status": idea.get("status", ""),
        "tasks": tasks,
        "done": done,
        "total": total,
        "progress": round(done / total, 3) if total else 0.0,
        "last": tasks[-1] if tasks else None,
    }


def recent(runtime_dir: str | Path, limit: int = 5) -> list[dict]:
    folder = Path(runtime_dir) / "ideas"
    if not folder.is_dir():
        return []
    rows = []
    for path in sorted(folder.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)[:limit]:
        payload = track(runtime_dir, path.stem)
        if payload is not None:
            rows.append(payload)
    return rows
