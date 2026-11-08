"""V5 GÖREV 010 — Departman beyni: gerçek kayıtlardan operasyonel görünüm.

Salt-okunur toplama: hedefler/kuyruk, müdür, işçiler, yetenek haritası, çalışan
görevler, engeller, QA/teslimat, paylaşılan bilgi, haftalık performans ve
departmanlar arası bağımlılıklar. Veri yoksa `null`/0; uydurma yok.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path


def _json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _lines(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _roster(runtime: Path) -> list[dict]:
    payload = _json(runtime / "departments.json", {"departments": []})
    return payload.get("departments") if isinstance(payload, dict) else payload


def _missions(runtime: Path) -> list[dict]:
    db = runtime / "company-service.db"
    if not db.is_file():
        return []
    with sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True) as con:
        rows = con.execute(
            "select mission_id, objective, status, updated_at, last_error, result_json "
            "from missions").fetchall()
    out = []
    for mission_id, objective, status, updated_at, error, raw in rows:
        result = {}
        try:
            result = json.loads(raw) if raw else {}
        except TypeError:
            result = {}
        out.append({"mission_id": mission_id, "objective": str(objective or "")[:160],
                    "status": status, "updated_at": str(updated_at or ""),
                    "error": str(error or "")[:120], "result": result})
    return out


def _deliveries(runtime: Path) -> list[dict]:
    candidates = [runtime.parents[1] / "deliverables",
                  runtime.parent / "deliverables", runtime / "deliverables"]
    root = next((path for path in candidates if path.is_dir()), candidates[0])
    rows = []
    for manifest in root.glob("*/manifest.json"):
        payload = _json(manifest, {})
        for contributor in payload.get("contributors") or []:
            rows.append({"delivery_id": payload.get("delivery_id"),
                         "department": contributor.get("department"),
                         "worker": contributor.get("worker"),
                         "task": contributor.get("task"),
                         "status": contributor.get("status"),
                         "verified_by": contributor.get("verified_by")})
    return rows


def snapshot(runtime, department_id: str) -> dict:
    runtime = Path(runtime)
    departments = _roster(runtime) or []
    department = next((d for d in departments
                       if d.get("department_id") == department_id), None)
    workers = (department or {}).get("workers") or []
    missions = [m for m in _missions(runtime)
                if department_id in str(m.get("result") or "")
                or m.get("result", {}).get("primary_department") == department_id]
    running = [m for m in missions if m["status"] == "running"]
    blocked = [m for m in missions if m["status"] == "blocked"]
    weekly = [m for m in missions if m["status"] == "completed"
              and m["updated_at"][:10] >= time.strftime("%Y-%m-%d", time.localtime(
                  time.time() - 7 * 86400))]
    deliveries = [d for d in _deliveries(runtime) if d.get("department") == department_id]
    shared = [row for row in _lines(runtime / "cognition" / "_shared.jsonl")
              if row.get("department") == department_id and row.get("verified")]
    dependencies = sorted({str(step.get("department"))
                           for m in missions for step in
                           (m.get("result") or {}).get("steps") or []
                           if step.get("department") and step.get("department") != department_id})
    capabilities = sorted({cap for worker in workers
                           for cap in (worker.get("capabilities") or [])})
    manager = next((worker for worker in workers
                    if "manager" in str(worker.get("role") or "").casefold()
                    or "mudur" in str(worker.get("role") or "").casefold()), None)
    return {
        "department_id": department_id,
        "name": str((department or {}).get("name") or department_id),
        "manager": (manager or {}).get("worker_id"),
        "workers": len(workers),
        "capability_map": capabilities,
        "missions": len(missions),
        "running": len(running),
        "blocked": len(blocked),
        "weekly_completed": len(weekly),
        "weekly_rate": round(len(weekly) / max(1, len(missions)), 3) if missions else None,
        "blocked_examples": [{"mission_id": m["mission_id"], "error": m["error"]}
                             for m in blocked[-5:]],
        "delivered_tasks": len(deliveries),
        "deliveries": deliveries[-5:],
        "shared_facts": len(shared),
        "dependencies": dependencies,
        "note": "null = kayıt yok; departman beyni salt-okunur toplar",
    }


def all_brains(runtime) -> list[dict]:
    return [snapshot(runtime, str(d.get("department_id")))
            for d in (_roster(Path(runtime)) or [])]
