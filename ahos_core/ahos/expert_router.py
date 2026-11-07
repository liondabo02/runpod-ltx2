"""G010 — Kanıta dayalı uzmanlık yönlendirme.

Görev için gerekli yetenekleri alır; işçileri şu ölçütlerle karşılaştırır:
yetenek kapsamı, doğrulanmış prosedürel başarı oranı, kanıt durumu ve iş yükü.
Departmanda uygun uzman yoksa çapraz departman desteği önerir.

Hiçbir seçim "başarı" sayılmaz; yalnız atama önerisidir ve gerekçesi kaydedilir.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from . import cognitive_memory as cm

BUSY_WINDOW_SECONDS = 600
RECENT_MISSION_KINDS = {"mission"}


def _departments(runtime) -> list[dict]:
    try:
        payload = json.loads((Path(runtime) / "departments.json").read_text(encoding="utf-8"))
        return payload.get("departments") if isinstance(payload, dict) else payload
    except (OSError, json.JSONDecodeError):
        return []


def _roster(runtime) -> list[dict]:
    rows = []
    for dep in _departments(runtime):
        dep_id = str(dep.get("department_id") or "")
        for worker in dep.get("workers") or []:
            wid = str(worker.get("worker_id") or "")
            if not wid:
                continue
            rows.append({
                "worker": wid, "department": dep_id,
                "name": str(worker.get("name") or wid),
                "capabilities": {str(cap).casefold() for cap in
                                 (worker.get("capabilities") or worker.get("skills") or [])},
            })
    return rows


def _profile(runtime, worker: str):
    try:
        return cm.load(runtime, worker)
    except ValueError:
        return None


def _rate(profile) -> float | None:
    if not profile:
        return None
    rows = profile["memory"].get("procedural") or []
    ok = sum(int(row.get("ok", 0)) for row in rows)
    fail = sum(int(row.get("fail", 0)) for row in rows)
    return round(ok / (ok + fail), 3) if ok + fail else None


def _busy(runtime, worker: str, now: float | None = None) -> bool:
    path = Path(runtime) / "minds" / f"{worker}.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    moment = time.time() if now is None else float(now)
    for event in reversed(payload.get("events") or []):
        if event.get("kind") not in RECENT_MISSION_KINDS:
            continue
        raw = str(event.get("at") or "")
        try:
            stamp = time.mktime(time.strptime(raw[:19], "%Y-%m-%dT%H:%M:%S"))
        except ValueError:
            continue
        return moment - stamp <= BUSY_WINDOW_SECONDS
    return False


def rank(runtime, required_skills: list[str], *, department: str | None = None,
         exclude: list[str] | None = None, now: float | None = None) -> list[dict]:
    """Uygun işçileri gerekçeli skorla sıralar; kanıtsız iddia üretmez."""

    wanted = [skill.casefold().strip() for skill in required_skills if skill and skill.strip()]
    if not wanted:
        return []
    excluded = set(exclude or [])
    ranked = []
    for row in _roster(runtime):
        if row["worker"] in excluded:
            continue
        matched = [skill for skill in wanted if skill in row["capabilities"]]
        if not matched:
            continue
        profile = _profile(runtime, row["worker"])
        rate = _rate(profile)
        evidence = str(((profile or {}).get("evidence") or {}).get("status") or "no_profile")
        busy = _busy(runtime, row["worker"], now)
        coverage = len(matched) / len(wanted)
        same_department = department is None or row["department"] == department
        score = round(
            coverage * 0.35
            + (rate if rate is not None else 0.4) * 0.25
            + (1.0 if evidence == "verified" else 0.15) * 0.20
            + (0.0 if busy else 1.0) * 0.20
            + (0.05 if same_department and department else 0.0), 4)
        reasons = [f"yetenek {len(matched)}/{len(wanted)}",
                   f"başarı {rate if rate is not None else 'kanıt yok'}",
                   f"kanıt {evidence}", "meşgul" if busy else "uygun",
                   "aynı departman" if same_department and department else "çapraz departman"]
        ranked.append({
            "worker": row["worker"], "department": row["department"],
            "name": row["name"], "matched_skills": matched,
            "rate": rate, "evidence": evidence, "busy": busy,
            "same_department": bool(department and same_department),
            "score": score, "reasons": reasons,
        })
    ranked.sort(key=lambda item: (item["score"], item["worker"]), reverse=True)
    return ranked


def route(runtime, required_skills: list[str], *, department: str | None = None,
          exclude: list[str] | None = None) -> dict:
    """En uygun uzmanı seçer; departman içi yoksa çapraz destek önerir."""

    candidates = rank(runtime, required_skills, department=department, exclude=exclude)
    if not candidates:
        record = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "event": "route.none",
                  "required_skills": required_skills, "department": department}
        _log(runtime, record)
        return {"selected": None, "candidates": [], "cross_department": False,
                "required_skills": required_skills,
                "rationale": "gerekli yeteneklere sahip işçi bulunamadı"}

    same = [item for item in candidates if item["same_department"]]
    selected = (same or candidates)[0]
    cross = not selected["same_department"] and bool(department)
    record = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "event": "route.selected",
              "required_skills": required_skills, "department": department,
              "selected": selected["worker"], "selected_department": selected["department"],
              "score": selected["score"], "cross_department": cross,
              "rationale": "; ".join(selected["reasons"])}
    _log(runtime, record)
    return {"selected": selected, "candidates": candidates[:5],
            "cross_department": cross, "required_skills": required_skills,
            "rationale": record["rationale"]}


def _log(runtime, record: dict) -> None:
    path = Path(runtime) / "cognition"
    path.mkdir(parents=True, exist_ok=True)
    with (path / "_routing.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
