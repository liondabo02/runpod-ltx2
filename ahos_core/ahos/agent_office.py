"""Ajan Ofisi — tek ekrandan tüm ajanları yönet ve işlerini görünür kıl.

Ajan Ofisi'nin (sarp07/Ajan-Ofisi) en değerli fikri: **bütün ajanlar tek yerden
yönetilir ve ne yaptıkları canlı görünür**. Burada bunun AHOS'a uygun, kompakt
karşılığı üretilir:

- `snapshot()`      : departman → işçi listesi, her işçinin son durumu, başarı
                      oranı, son çalışma zamanı, o an ne yaptığı
- `feed()`          : canlı olay akışı (görev başladı/bitti/engellendi)
- `worklog()`       : "kaldığın yerden devam" notu (departman başına)
- `approvals()`     : sahibin onayını bekleyen işler
"""

from __future__ import annotations

import json
import math
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import worker_state


def _db(runtime: Path) -> Path:
    return runtime / "company-service.db"


def _rows(runtime: Path, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    db = _db(runtime)
    if not db.exists():
        return []
    try:
        with sqlite3.connect(db) as con:
            con.row_factory = sqlite3.Row
            return list(con.execute(sql, params))
    except sqlite3.Error:
        return []


def worker_stats(runtime_dir: str | Path, limit: int = 4000) -> dict[str, dict]:
    """İşçi başına koşu sayısı, başarı oranı ve son aktivite."""

    runtime = Path(runtime_dir)
    ledger = runtime / "worker-metrics.jsonl"
    stats: dict[str, dict] = {}
    if not ledger.exists():
        return stats
    for line in ledger.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict) or not isinstance(row.get('success'), bool):
            continue
        worker = str(row.get("worker_id") or "")
        if not worker:
            continue
        item = stats.setdefault(worker, {"runs": 0, "ok": 0, "last": "", "seconds": []})
        item["runs"] += 1
        item["ok"] += 1 if row.get("success") else 0
        item["last"] = str(row.get("at") or item["last"])
        duration = row.get('duration_ms')
        if duration is None:
            duration = row.get('seconds')
            scale = 1
        else:
            scale = 1000
        if isinstance(duration, (int, float)) and not isinstance(duration, bool) and math.isfinite(duration) and duration >= 0:
            item['seconds'].append(float(duration) / scale)
    for item in stats.values():
        seconds = item.pop("seconds", [])
        item["rate"] = round(item["ok"] / item["runs"], 3) if item["runs"] else 0.0
        item["avg_seconds"] = round(sum(seconds) / len(seconds), 1) if seconds else 0.0
    return stats


def _mission_status(runtime: Path) -> dict[str, list[dict]]:
    """Departman → aktif/son görevler."""

    rows = _rows(
        runtime,
        "select mission_id, objective, primary_department, status, updated_at, last_error "
        "from missions order by case when status='running' then 0 else 1 end, updated_at desc limit 400",
    )
    by_department: dict[str, list[dict]] = {}
    for row in rows:
        by_department.setdefault(str(row["primary_department"]), []).append(
            {
                "mission_id": row["mission_id"],
                "objective": (row["objective"] or "")[:120],
                "status": row["status"],
                "updated_at": row["updated_at"],
                "error": (row["last_error"] or "")[:160],
            }
        )
    return by_department


def _worker_activity(current: dict | None, status: str | None) -> str:
    if status == "running":
        return "çalışıyor"
    if status == "pending":
        return "sırada"
    if status == "blocked":
        return "engellendi"
    if current and current.get("last"):
        return "beklemede"
    return "boşta"


def snapshot(runtime_dir: str | Path) -> dict:
    """Tek ekran için tam durum: departmanlar, işçiler, canlı görevler, olaylar."""

    runtime = Path(runtime_dir)
    stats = worker_stats(runtime)
    missions = _mission_status(runtime)
    counts = {}
    for row in _rows(runtime, 'select primary_department,status,count(*) as n from missions group by primary_department,status'):
        counts.setdefault(str(row['primary_department']), {})[row['status']] = row['n']
    observed = _observed_workers(runtime, missions)

    book_path = runtime / "departments.json"
    departments: list[dict] = []
    try:
        payload = json.loads(book_path.read_text(encoding="utf-8"))
        raw = payload.get("departments") if isinstance(payload, dict) else payload
        raw = raw or []
    except (OSError, json.JSONDecodeError):
        raw = []

    for dep in raw:
        if not isinstance(dep, dict):
            continue
        dep_id = str(dep.get("department_id") or "")
        dep_missions = missions.get(dep_id, [])
        active = next((m for m in dep_missions if m["status"] == "running"), None)
        if active:
            try:
                from .agent_control import ticket_for

                active["ticket"] = ticket_for(runtime, active["mission_id"])
            except Exception:  # noqa: BLE001 - bilet isteğe bağlı
                active["ticket"] = ""
        dep_counts = counts.get(dep_id, {})
        pending = dep_counts.get('pending', 0)
        blocked = dep_counts.get('blocked', 0)
        completed = dep_counts.get('completed', 0)
        workers: list[dict] = []
        for worker in dep.get("workers") or []:
            if not isinstance(worker, dict):
                continue
            wid = str(worker.get("worker_id") or "")
            st = stats.get(wid, {})
            observed_row = observed.get(wid) or {}
            state = worker_state.derive(
                runtime, wid,
                observed_task=str(observed_row.get("task_id") or ""),
                last_active=str(st.get("last") or ""),
            )
            workers.append(
                {
                    "worker_id": wid,
                    "name": worker.get("name") or wid,
                    "role": worker.get("role") or "",
                    "rate": st.get("rate", 0.0),
                    "runs": st.get("runs", 0),
                    "avg_seconds": st.get("avg_seconds", 0.0),
                    "last_run": st.get("last", ""),
                    "state": state["label"],
                    "state_code": state["state"],
                    "state_reason": state["reason"],
                    "stale": state["stale"],
                    "unknown": state["unknown"],
                    "activity_verified": wid in observed,
                    "active_task": observed.get(wid),
                    "skills": list(worker.get("capabilities") or [])[:4],
                    "owner": "sahip" if worker.get("reports_to") is None else str(worker.get("reports_to")),
                }
            )
        departments.append(
            {
                "department_id": dep_id,
                "name": dep.get("name") or dep_id,
                "mission": (dep.get("mission") or "")[:140],
                "workers": workers,
                "active": active,
                "pending": pending,
                "blocked": blocked,
                "completed": completed,
                "state": "çalışıyor" if active else ("bekliyor" if pending else "boşta"),
            }
        )

    departments.sort(key=lambda item: (item["state"] != "çalışıyor", -item["completed"]))
    worker_rows = [worker for item in departments for worker in item["workers"]]
    totals = {
        "departments": len(departments),
        "workers": sum(len(item["workers"]) for item in departments),
        "running": sum(v.get('running', 0) for v in counts.values()),
        "pending": sum(v.get('pending', 0) for v in counts.values()),
        "blocked": sum(v.get('blocked', 0) for v in counts.values()),
        "completed": sum(v.get('completed', 0) for v in counts.values()),
        "verified_active_workers": len(observed),
        "states": worker_state.counts(worker_rows, key="state_code"),
        "unknown_workers": sum(1 for worker in worker_rows if worker["unknown"]),
        "stale_workers": sum(1 for worker in worker_rows if worker["stale"]),
    }
    try:
        from .atrium import attention_counts, chronicle, needs_attention, title_text

        items = needs_attention(runtime)
        counts = attention_counts(items)
        attention = {"items": items, "counts": counts, "title": title_text(counts)}
        chronicle_items = chronicle(runtime, limit=12)
    except Exception:  # noqa: BLE001 - ön masa isteğe bağlı
        attention, chronicle_items = {"items": [], "counts": {}, "title": ""}, []

    return {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "totals": totals,
        "attention": attention,
        "chronicle": chronicle_items,
        "departments": departments,
        "feed": feed(runtime, limit=12),
        "approvals": approvals(runtime),
    }


def roster_index(runtime_dir: str | Path) -> dict[str, dict]:
    """İşçi kimliği → ad/rol/departman (3D ofisin `/api/roster` kaynağı)."""

    runtime = Path(runtime_dir)
    try:
        payload = json.loads((runtime / "departments.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    departments = payload.get("departments") if isinstance(payload, dict) else payload
    index: dict[str, dict] = {}
    for department in departments or []:
        if not isinstance(department, dict):
            continue
        dep_id = str(department.get("department_id") or "")
        for worker in department.get("workers") or []:
            if not isinstance(worker, dict):
                continue
            wid = str(worker.get("worker_id") or "")
            if wid:
                index[wid] = {"name": str(worker.get("name") or wid),
                              "role": str(worker.get("role") or ""),
                              "department": dep_id}
    return index


def _observed_workers(runtime: Path, missions: dict) -> dict:
    """Read real step events; a department running is not worker evidence.

    Cross-process events must be recent and match a currently running mission.
    Missing/stale events leave the worker unverified instead of animating it.
    """
    from datetime import datetime, timezone
    running = {m['mission_id'] for rows in missions.values() for m in rows if m['status'] == 'running'}
    events = {}
    try:
        lines = (runtime / 'live-events.jsonl').read_text(encoding='utf-8', errors='replace').splitlines()[-500:]
    except OSError:
        lines = []
    for line in lines:
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict) and event.get('worker_id') and event.get('kind') in {'step_started', 'step_finished'}:
            events[str(event['worker_id'])] = event
    result = {}
    now = datetime.now(timezone.utc)
    for worker, event in events.items():
        if event['kind'] != 'step_started':
            continue
        mission = str(event.get('mission_id') or '')
        if not any(mission == m or mission.startswith(m + ':') for m in running):
            continue
        try:
            stamp = datetime.fromisoformat(str(event.get('at') or '').replace('Z', '+00:00'))
            age = (now - stamp).total_seconds()
        except (ValueError, TypeError):
            continue
        if 0 <= age <= 180:
            result[worker] = {'task_id': mission, 'step_id': event.get('step_id', ''), 'observed_at': event['at']}
    return result


def feed(runtime_dir: str | Path, *, limit: int = 20) -> list[dict]:
    """Canlı akış: son görev olayları (başladı/bitti/engel)."""

    runtime = Path(runtime_dir)
    events: list[dict] = []
    audit = runtime / "audit.jsonl"
    if audit.exists():
        for line in audit.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            payload = row.get("payload") or {}
            events.append(
                {
                    "at": row.get("timestamp") or row.get("at") or "",
                    "event": row.get("event_type") or row.get("event") or "",
                    "mission": row.get("correlation_id") or row.get("mission_id") or "",
                    "detail": str(
                        payload.get("reason") or payload.get("objective") or payload.get("status") or ""
                    )[:120],
                }
            )
    if events:
        return events[::-1]

    rows = _rows(
        runtime,
        "select mission_id, status, updated_at, primary_department from missions "
        "order by updated_at desc limit ?",
        (limit,),
    )
    return [
        {
            "at": row["updated_at"],
            "event": f"mission.{row['status']}",
            "mission": row["mission_id"],
            "detail": row["primary_department"],
        }
        for row in rows
    ]


def approvals(runtime_dir: str | Path, *, limit: int = 10) -> list[dict]:
    """Sahibin onayını bekleyen işler (engel nedeni onay/izin içerenler)."""

    rows = _rows(
        runtime_dir,
        "select mission_id, objective, primary_department, last_error from missions "
        "where status='blocked' and (lower(last_error) like '%onay%' "
        "or lower(last_error) like '%izin%' or lower(last_error) like '%approval%') limit ?",
        (limit,),
    )
    return [
        {
            "mission_id": row["mission_id"],
            "objective": (row["objective"] or "")[:120],
            "department": row["primary_department"],
            "reason": (row["last_error"] or "")[:140],
        }
        for row in rows
    ]


def worklog_path(runtime_dir: str | Path, department: str) -> Path:
    directory = Path(runtime_dir) / "worklog"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{department}.md"


def write_worklog(runtime_dir: str | Path, department: str, note: str) -> Path:
    """Departman için 'kaldığın yerden devam' notu."""

    path = worklog_path(runtime_dir, department)
    stamp = time.strftime("%Y-%m-%d %H:%M")
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"\n## {stamp}\n{note.strip()}\n")
    return path


def read_worklog(runtime_dir: str | Path, department: str, limit: int = 1200) -> str:
    path = worklog_path(runtime_dir, department)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")[-limit:]
