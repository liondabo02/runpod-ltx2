"""V5 GÖREV 019 — İşçi kartı: gerçek kayıtlardan özgeçmiş/performans görünümü.

Özel hafıza metinleri varsayılan olarak gizlenir; yalnız sayılar ve sonuçlar
gösterilir. Kart hiçbir veriyi değiştirmez.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import cognitive_memory as cm


def _json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _roster(runtime: Path) -> dict:
    payload = _json(runtime / "departments.json", {"departments": []})
    departments = payload.get("departments") if isinstance(payload, dict) else payload
    for department in departments or []:
        for worker in department.get("workers") or []:
            if worker.get("worker_id"):
                yield {**worker, "department": department.get("department_id")}


def _artifacts(runtime: Path, worker: str) -> list[dict]:
    candidates = [runtime.parents[1] / "deliverables",
                  runtime.parent / "deliverables", runtime / "deliverables"]
    root = next((path for path in candidates if path.is_dir()), candidates[0])
    rows = []
    for manifest in root.glob("*/manifest.json"):
        payload = _json(manifest, {})
        for contributor in payload.get("contributors") or []:
            if contributor.get("worker") == worker:
                rows.append({"delivery_id": payload.get("delivery_id"),
                             "task": contributor.get("task"),
                             "status": contributor.get("status")})
    return rows[-5:]


def card(runtime, worker: str, *, include_private: bool = False) -> dict:
    runtime = Path(runtime)
    roster = next((row for row in _roster(runtime) if row["worker_id"] == worker), {})
    profile = cm.load(runtime, worker, str(roster.get("department") or ""))
    mind = _json(runtime / "minds" / f"{worker}.json", {})
    memory = profile.get("memory") or {}
    emotional = profile.get("emotion") or {}
    errors = memory.get("error_memory") or []
    collab = memory.get("collaboration_memory") or []
    result = {
        "worker_id": worker,
        "name": roster.get("name") or worker,
        "role": roster.get("role"),
        "department": roster.get("department"),
        "capabilities": list(roster.get("capabilities") or [])[:6],
        "current_task": (memory.get("working") or {}).get("objective"),
        "verified_successes": len((profile.get("evidence") or {})
                                  .get("verified_missions") or []),
        "learned_methods": len(memory.get("procedural") or []),
        "semantic_facts": len(memory.get("semantic") or []),
        "collaboration_count": len(collab),
        "last_collaboration": collab[-1]["helper"] if collab else None,
        "last_error": errors[-1]["cause"] if errors else None,
        "last_qa": (profile.get("meta_memory", {}).get("mission_qa") or {}).get(
            "reliability"),
        "emotion": {key: round(float(value), 2) for key, value in emotional.items()
                    if isinstance(value, (int, float))},
        "last_active": max((str(event.get("at") or "") for event in
                            mind.get("events") or []), default=""),
        "artifacts": _artifacts(runtime, worker),
        "private_memory_hidden": not include_private,
    }
    if include_private:
        result["private"] = {"episodic": memory.get("episodic") or [],
                             "semantic": memory.get("semantic") or [],
                             "errors": errors, "collaboration": collab}
    return result
