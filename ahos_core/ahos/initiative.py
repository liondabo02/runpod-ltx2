"""Otonom girişim — her turda en zayıf departmana hedef üretir.

- tick(runtime_dir, departments) -> dict
  · kuyruk pending < 8 ise: en zayıf departmanı seç (training-report)
  · hedef metni üret: "<departman> için iyileştirme"
  · skor = (etki * olasılık) / maliyet = 0.8
  · runtime/initiative.jsonl dosyasına append: {at, department, goal, score}
  · dönüş: {"created": n, "department": dep, "score": s}
- last(runtime_dir) -> son kaydı döndür
"""

from __future__ import annotations

import json
import time
from pathlib import Path


def _weakest_department(runtime_dir: str | Path) -> str | None:
    """En zayıf departmanı training-report'ten bul."""
    report_path = Path(runtime_dir).parent / "config" / "training-report.json"
    if not report_path.exists():
        return None
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if report.get("departments", 0) > 0 and report.get("workers", 0) > 0:
            results = report.get("results", [])
            if results:
                weakest = min(results, key=lambda r: r.get("score", 101))
                return weakest.get("department")
    except (json.JSONDecodeError, OSError):
        pass
    return None


def tick(runtime_dir: str | Path, departments: list[dict]) -> dict:
    """Eğer kuyruk pending < 8 ise en zayıf departmana hedef üret."""
    runtime = Path(runtime_dir)
    pending_path = runtime / "mission-stats.json"

    from .queue_budget import MAX_PENDING_MISSIONS, AUTONOMOUS_RESUME_BELOW, pending_count

    pending = pending_count(runtime)
    source = "sqlite"
    if pending is None:
        # Legacy offline simulations used mission-stats.json. It can inform
        # an idea-only proposal, never authority to enqueue a real mission.
        source = "legacy_stats"
        try:
            pending = int(json.loads(pending_path.read_text(encoding="utf-8"))["pending"])
        except (OSError, ValueError, KeyError, TypeError):
            pending, source = MAX_PENDING_MISSIONS, "unavailable"

    created = 0
    department = None
    goal = ""
    score = 0.8

    if pending < min(8, AUTONOMOUS_RESUME_BELOW) and source != "unavailable":
        dep = _weakest_department(runtime)
        if dep:
            department = dep
            goal = f"{dep} için iyileştirme"
            created = 1

    # initiative.jsonl'a kaydet
    log_path = runtime / "initiative.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "department": department or "",
        "goal": goal,
        "score": score,
        "pending": pending,
        "pending_source": source,
        "capacity_limit": MAX_PENDING_MISSIONS,
        "queue_backpressure": pending >= AUTONOMOUS_RESUME_BELOW,
        "note": "idea-only; no actual mission enqueued",
    }
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    return {"created": created, "department": department or "", "score": score}


def last(runtime_dir: str | Path) -> dict | None:
    """initiative.jsonl'dan son kaydı döndür."""
    runtime = Path(runtime_dir)
    log_path = runtime / "initiative.jsonl"
    if not log_path.exists():
        return None
    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        if not lines:
            return None
        last_line = lines[-1]
        return json.loads(last_line)
    except (json.JSONDecodeError, OSError):
        return None
