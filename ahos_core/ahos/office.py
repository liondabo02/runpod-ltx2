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
        con = sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True)
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


def _projects(runtime: Path) -> list[dict]:
    """Projeler: tek çalışma alanında hangi iş nerede, kapısı var mı."""

    import json as _json

    try:
        payload = _json.loads((runtime / "projects.json").read_text(encoding="utf-8"))
    except (OSError, _json.JSONDecodeError):
        return []
    items = payload.get("projects") if isinstance(payload, dict) else payload
    result: list[dict] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        path = Path(str(item.get("path") or ""))
        result.append(
            {
                "name": str(item.get("name") or ""),
                "department": str(item.get("department_id") or ""),
                "path": str(path),
                "gate": (path / "tools" / "check_offline.py").is_file(),
            }
        )
    return result


MEDIA_SUFFIXES = {".mp4", ".webm", ".mov", ".wav", ".mp3", ".m4a", ".png", ".jpg", ".jpeg"}


def _products(runtime: Path) -> list[dict]:
    folder = runtime / "products"
    if not folder.is_dir():
        return []
    rows = []
    for path in sorted(folder.iterdir(), key=lambda item: item.stat().st_mtime, reverse=True):
        if path.is_dir():
            files = [p for p in path.glob("*") if p.is_file()]
            media = [p for p in files if p.suffix.lower() in MEDIA_SUFFIXES and p.stat().st_size > 1024]
            # "doğrulandı" için manifest YETMEZ: en az bir gerçek medya dosyası şart.
            rows.append(
                {
                    "name": path.name,
                    "files": len(files),
                    "media": len(media),
                    "validated": False,
                    "artifact_kind": "media_package" if media else "document_package",
                    "manifest_present": (path / "manifest.json").is_file(),
                }
            )
    return rows[:10]


def _tracks(runtime: Path) -> list[dict]:
    try:
        from .tracking import recent

        return recent(runtime, 5)
    except Exception:  # noqa: BLE001 - takip isteğe bağlı
        return []


def _queue_delivery_rate(runtime_dir: Path) -> float:
    """Kuyruk tabanlı teslim oranı (8766 paneliyle aynı tanım)."""

    import sqlite3

    db = Path(runtime_dir) / "company-service.db"
    if not db.exists():
        return 0.0
    try:
        with sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True) as con:
            row = con.execute(
                "select "
                "sum(case when status='completed' then 1 else 0 end), "
                "sum(case when status!='cancelled' then 1 else 0 end) "
                "from missions"
            ).fetchone()
        completed, real_total = int(row[0] or 0), int(row[1] or 0)
        return round(completed / real_total, 3) if real_total else 0.0
    except sqlite3.Error:
        return 0.0


def build(runtime_dir: str | Path) -> dict:
    runtime = Path(runtime_dir)
    activity = _activity(runtime)
    departments = _departments(runtime)
    from .department_operations import operating_contracts
    from .live_activity import active
    contracts = operating_contracts(departments)
    active_workers = active()
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
            status = "working" if worker_id in active_workers else "idle"
            workers.append(
                {
                    "id": worker_id,
                    "name": str(worker.get("name") or worker_id),
                    "role": str(worker.get("role") or ""),
                    "avatar": AVATARS[(index + worker_index) % len(AVATARS)],
                    "status": status,
                    "activity_verified": worker_id in active_workers,
                    "mood": brain.get("mood", "calm"),
                    "thought": last_thought.get("text", "") if worker_id in active_workers else "",
                    "last_recorded_thought": last_thought.get("text", ""),
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
                "operations": contracts.get(department_id, {}),
            }
        )

    # Rendering the office never mutates worker memory or invents activity.

    return {
        "generated_at": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"),
        "holding": {
            "daemon": activity["daemon"].get("status", "unknown"),
            "operating_contracts": contracts,
            "activity_scope": "verified_in_process_only",
            "executor": activity["daemon"].get("executor_mode", ""),
            "quality": activity["quality"],
            # 8766 başkanlık paneliyle aynı formül: completed / (cancelled hariç)
            "queue_rate": _queue_delivery_rate(runtime),
            "pending_ideas": activity["pending_ideas"],
            "last_task": str(last_mission.get("mission_id") or ""),
            "infra": activity["daemon"].get("infra", {}),
            "knowledge": _knowledge_stats(runtime),
            "lessons": _lesson_count(runtime),
            "recent": _recent_missions(runtime),
            "goals": _goal_progress(runtime),
            "projects": _projects(runtime),
            "products": _products(runtime),
            "tracks": _tracks(runtime),
        },
        "rooms": rooms,
    }
