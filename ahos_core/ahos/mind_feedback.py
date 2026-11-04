"""Beyin geri beslemesi: plan→görev dönüşümü ve sonuçların işçi zihnine yazılması."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from .autonomous_company import PersistentMissionQueue
from .outcome import record as outcome_record
from .worker_mind import load, save


def _plan_queue(runtime: Path) -> Path:
    return runtime / "minds" / "plan-queue.jsonl"


def flush_plan_queue(runtime_dir, limit: int = 10) -> dict:
    """Plan adımlarını (state=pending) gerçek görevlere çevirir."""

    runtime = Path(runtime_dir)
    path = _plan_queue(runtime)
    if not path.exists():
        return {"created": 0}

    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    pending = [entry for entry in entries if entry.get("state") == "pending"]
    if not pending:
        return {"created": 0}

    queue = PersistentMissionQueue(runtime / "company-service.db")
    stamp = int(time.time())
    created = 0

    for index, entry in enumerate(pending[:limit]):
        department = str(entry.get("department") or "genel")
        action = str(entry.get("action") or "plan adımı")
        worker = str(entry.get("worker") or "")
        mission_id = f"CMD-{department}-plan-{stamp}-{index}"
        try:
            queue.enqueue(
                mission_id=mission_id,
                objective=f"{department} · {action} (işçi: {worker})",
                primary_department=department,
                max_attempts=1,
                replace_existing=True,
            )
            entry.update({"state": "queued", "mission_id": mission_id,
                          "queued_at": time.strftime("%Y-%m-%dT%H:%M:%S")})
            created += 1
        except Exception as exc:  # noqa: BLE001
            entry.update({"state": "error", "error": type(exc).__name__})

    path.write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in entries) + "\n", encoding="utf-8")
    return {"created": created, "pending": len(pending)}


def feedback(runtime_dir, worker_id: str, department: str, ok: bool, duration_s: float = 0.0) -> dict:
    """Görev sonucunu hem outcome'a hem işçi zihnine yaz (öğrenme döngüsü)."""

    runtime = Path(runtime_dir)
    result = outcome_record(runtime, department, ok, duration_s)

    mind = load(runtime, worker_id, department)
    mind.events.append({
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "kind": "mission",
        "detail": f"{department} görevi {'tamam' if ok else 'başarısız'}",
        "ok": bool(ok),
    })
    mind.self_model = dict(mind.self_model or {})
    mind.self_model["success_rate"] = mind.success_rate
    save(runtime, mind)
    return result
