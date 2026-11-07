"""V5 GÖREV 012 — Onaylı hedef → plan → görev grafiği → kuyruk.

Yalnız `approved_by="harun"` hedefi kabul edilir. Görev kimlikleri hedeften
türetilir (idempotent); tamamlanmış görev geri açılmaz. Kuyruk kapasitesi
korunur; hata durumunda hiçbir görev yarım yazılmaz.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from . import cognitive_memory as cm
from .autonomous_company import PersistentMissionQueue


def _mission_id(goal: str, index: int) -> str:
    digest = hashlib.sha256(goal.encode("utf-8")).hexdigest()[:10]
    return f"CMD-GOAL-{digest}-{index + 1:02d}"


def intake(runtime, *, goal: str, tasks: list[dict], approved_by: str = "",
           department: str = "holding") -> dict:
    if str(approved_by).strip().casefold() != "harun":
        raise PermissionError("only Harun-approved goals may create missions")
    goal = str(goal).strip()
    if not goal or not tasks:
        raise ValueError("goal and at least one task are required")
    if len(tasks) > 20:
        raise ValueError("task graph too large (max 20)")
    runtime = Path(runtime)
    queue = PersistentMissionQueue(runtime / "company-service.db")
    profile = cm.load(runtime, "ceo-01", "holding")
    plans = cm.build_plans(profile, goal=goal, candidates=[
        {"name": "kontrollu", "steps": [str(t["objective"])[:120] for t in tasks],
         "risk": 0.2, "success_probability": 0.85, "estimated_cost_usd": 0.0,
         "verification": "bağımsız QA", "evidence_score": 0.8},
        {"name": "hizli", "steps": [str(t["objective"])[:120] for t in tasks],
         "risk": 0.5, "success_probability": 0.7, "estimated_cost_usd": 0.0,
         "verification": "QA", "evidence_score": 0.4},
        {"name": "arastirmali", "steps": [str(t["objective"])[:120] for t in tasks],
         "risk": 0.3, "success_probability": 0.75, "estimated_cost_usd": 0.0,
         "verification": "kaynak + QA", "evidence_score": 0.6},
    ])
    created, skipped = [], []
    for index, task in enumerate(tasks):
        mission_id = _mission_id(goal, index)
        existing = queue.get(mission_id)
        if existing is not None:
            skipped.append({"mission_id": mission_id, "status": existing.status.value})
            continue
        queue.enqueue(mission_id=mission_id, objective=str(task["objective"])[:400],
                      primary_department=str(task.get("department") or department),
                      max_attempts=int(task.get("max_attempts") or 2))
        created.append({"mission_id": mission_id,
                        "department": str(task.get("department") or department),
                        "depends_on": list(task.get("depends_on") or [])})
    return {"goal": goal, "approved_by": "harun", "chosen_plan": plans["chosen"],
            "rationale": plans["rationale"], "created": created, "skipped": skipped,
            "pending_now": len([m for m in queue.list()
                                if m.status.value == "pending"])}
