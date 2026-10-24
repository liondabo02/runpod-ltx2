"""Office state: who is where, what they are doing, what they are thinking.

The viewer is a live picture of the holding: rooms per department, one avatar
per worker, live status, last activity and the worker's current thought. All of
it is derived from files the holding already writes; nothing is invented.
"""

from __future__ import annotations

import json
from pathlib import Path

from .brain import load as load_brain
from .failure_analytics import analyse

AVATARS = ("🧑‍💻", "👩‍💻", "🧑‍🔬", "👩‍🔬", "🧑‍🎨", "👩‍🎨", "🧑‍🏫", "👩‍🏫", "🧑‍🚀", "👩‍🚀")


def _read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return rows
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _departments(runtime: Path) -> list[dict]:
    try:
        payload = json.loads((runtime / "departments.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    departments = payload.get("departments") if isinstance(payload, dict) else payload
    return [item for item in departments or [] if isinstance(item, dict)]


def _activity(runtime: Path) -> dict:
    autonomy = {}
    try:
        autonomy = json.loads((runtime / "autonomy-state.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass
    daemon = {}
    try:
        daemon = json.loads((runtime / "daemon-state.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass
    missions = _read_jsonl(runtime / "daemon-missions.jsonl")[-10:]
    ideas = list((runtime / "ideas").glob("*.json")) if (runtime / "ideas").is_dir() else []
    pending_ideas = 0
    for path in ideas:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for task in payload.get("tasks") or []:
            if task.get("status") == "pending":
                pending_ideas += 1
    return {
        "daemon": daemon,
        "autonomy": autonomy,
        "missions": missions,
        "pending_ideas": pending_ideas,
        "quality": analyse(runtime),
    }


def _knowledge_stats(runtime: Path) -> dict:
    try:
        from .knowledge import stats

        return stats(runtime)
    except Exception:  # noqa: BLE001 - knowledge is optional
        return {"documents": 0, "chunks": 0}


def _lesson_count(runtime: Path) -> int:
    path = runtime / "knowledge" / "lessons.jsonl"
    try:
        return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    except OSError:
        return 0


def _recent_missions(runtime: Path, limit: int = 6) -> list[dict]:
    """Son görevler: sahibin verdiği işin durumunu ofiste gösterir."""

    import json as _json
    import re as _re
    import sqlite3

    db = runtime / "company-service.db"
    if not db.is_file():
        return []
    try:
        con = sqlite3.connect(str(db))
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "select objective,status,updated_at,result_json from missions order by rowid desc limit ?",
            (limit,),
        ).fetchall()
        con.close()
    except sqlite3.Error:
        return []
    result: list[dict] = []
    for row in rows:
        try:
            payload = _json.loads(row["result_json"] or "{}")
        except _json.JSONDecodeError:
            payload = {}
        summary = " ".join(
            str(step.get("worker_summary") or "") for step in payload.get("steps") or []
        )
        match = _re.search(r"(\d+) dosya değişti", summary)
        result.append(
            {
                "objective": str(row["objective"])[:120],
                "status": str(row["status"]),
                "changed": int(match.group(1)) if match else 0,
                "at": str(row["updated_at"] or "")[11:19],
            }
        )
    return result


def _goal_progress(runtime: Path) -> list[dict]:
    try:
        from .goals import progress

        return progress(runtime)[:3]
    except Exception:  # noqa: BLE001 - hedefler isteğe bağlı
        return []


def build(runtime_dir: str | Path) -> dict:
    runtime = Path(runtime_dir)
    activity = _activity(runtime)
    departments = _departments(runtime)
    last_mission = activity["missions"][-1] if activity["missions"] else {}
    running = str(activity["daemon"].get("status") or "") in {"running", "idle", "quota_wait"}

    rooms: list[dict] = []
    for index, department in enumerate(departments):
        department_id = str(department.get("department_id") or "")
        workers: list[dict] = []
        for worker_index, worker in enumerate(department.get("workers") or []):
            if not isinstance(worker, dict):
                continue
            worker_id = str(worker.get("worker_id") or "")
            if not worker_id:
                continue
            brain = load_brain(runtime, worker_id)
            last_thought = (brain.get("thoughts") or [{}])[-1]
            last_idea = (brain.get("ideas") or [{}])[-1]
            status = "working" if running and last_mission.get("status") == "routed" else "idle"
            if str(worker.get("role") or "").lower().startswith("manager"):
                status = "coordinating" if running else "idle"
            workers.append(
                {
                    "id": worker_id,
                    "name": str(worker.get("name") or worker_id),
                    "role": str(worker.get("role") or ""),
                    "avatar": AVATARS[(index + worker_index) % len(AVATARS)],
                    "status": status,
                    "mood": brain.get("mood", "calm"),
                    "thought": last_thought.get("text", ""),
                    "idea": last_idea.get("text", ""),
                    "memories": len(brain.get("memories") or []),
                    "delivered": int(activity["quality"].get("delivered") or 0)
                    if index == 0
                    else 0,
                }
            )
        rooms.append(
            {
                "id": department_id,
                "name": str(department.get("name") or department_id),
                "mission": str(department.get("mission") or ""),
                "workers": workers,
            }
        )

    # Her istekte en fazla üç işçi "düşünür": beyinleri canlı kalsın, dosya
    # yükü sınırlı olsun.
    flat = [(room, worker) for room in rooms for worker in room["workers"]]
    if flat:
        import time as _time

        from .brain import reflect

        quality = activity["quality"].get("delivery_rate", 0.0)
        offset = int(_time.time()) % len(flat)
        for step in range(min(3, len(flat))):
            room, worker = flat[(offset + step) % len(flat)]
            context = {
                "department": room["id"],
                "role": worker["role"],
                "pending": activity["pending_ideas"] + 1,
                "failures": int(activity["quality"].get("mission_failures") or 0),
                "delivered": int(activity["quality"].get("delivered") or 0),
                "last_task": str(last_mission.get("mission_id") or ""),
                "quality_rate": quality,
            }
            updated = reflect(runtime, worker["id"], context)
            worker["thought"] = (updated.get("thoughts") or [{}])[-1].get("text", "")
            worker["idea"] = (updated.get("ideas") or [{}])[-1].get("text", "")
            worker["mood"] = updated.get("mood", worker.get("mood", "calm"))

    return {
        "generated_at": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"),
        "holding": {
            "daemon": activity["daemon"].get("status", "unknown"),
            "executor": activity["daemon"].get("executor_mode", ""),
            "quality": activity["quality"],
            "pending_ideas": activity["pending_ideas"],
            "last_task": str(last_mission.get("mission_id") or ""),
            "infra": activity["daemon"].get("infra", {}),
            "knowledge": _knowledge_stats(runtime),
            "lessons": _lesson_count(runtime),
            "recent": _recent_missions(runtime),
            "goals": _goal_progress(runtime),
        },
        "rooms": rooms,
    }
