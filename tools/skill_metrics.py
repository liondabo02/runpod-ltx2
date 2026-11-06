"""İşçi bazında gerçek beceri metrikleri ve öğrenme öncesi/sonrası karşılaştırma.

Kaynaklar yalnız gözlenmiş kayıtlardır:
- `runtime/worker-metrics.jsonl` → koşu, başarı, süre, adım
- `company-service.db` → görev denemeleri ve sonuçları
- `runtime/cognition/_collective.jsonl` → yardım verme/alma
- `runtime/learning/*.jsonl` → ilk öğrenme zamanı
- `runtime/cognition/<worker>.json` → bilgi/kanıt durumu

Yetersiz örneklemde `null` yazılır; uydurma iyileşme raporlanmaz.

Kullanım:
    python tools/skill_metrics.py
    python tools/skill_metrics.py --learning-impact
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "ahos_core"
RUNTIME = CORE / "runtime"
DB = RUNTIME / "company-service.db"
REPORT = RUNTIME / "reports" / "skill-metrics.json"
sys.path.insert(0, str(CORE))


def _lines(path: Path) -> list[dict]:
    rows = []
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _metrics_rows() -> dict[str, dict]:
    stats: dict[str, dict] = {}
    for row in _lines(RUNTIME / "worker-metrics.jsonl"):
        worker = str(row.get("worker_id") or "")
        if not worker:
            continue
        rec = stats.setdefault(worker, {"runs": 0, "success": 0, "duration_ms": 0.0,
                                        "last_at": "", "departments": set(), "steps": set()})
        rec["runs"] += 1
        rec["success"] += 1 if row.get("success") is True else 0
        rec["duration_ms"] += float(row.get("duration_ms") or 0.0)
        rec["last_at"] = max(rec["last_at"], str(row.get("at") or ""))
        if row.get("department"):
            rec["departments"].add(str(row["department"]))
        if row.get("step_id"):
            rec["steps"].add(str(row["step_id"]))
    return stats


def _mission_stats() -> dict[str, dict]:
    stats: dict[str, dict] = {}
    if not DB.is_file():
        return stats
    with sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True) as con:
        rows = con.execute(
            "select mission_id, status, attempts, last_error, result_json, updated_at "
            "from missions where result_json is not null").fetchall()
    for mission_id, status, attempts, error, raw, updated_at in rows:
        try:
            payload = json.loads(raw)
        except TypeError:
            continue
        workers = {str(step.get("worker_id")) for step in payload.get("steps") or []
                   if step.get("worker_id")}
        for worker in workers:
            rec = stats.setdefault(worker, {"missions": 0, "completed": 0, "blocked": 0,
                                            "failed": 0, "first_attempt_ok": 0,
                                            "rework": 0, "causes": Counter(),
                                            "last_at": "", "mission_ids": []})
            rec["missions"] += 1
            rec["mission_ids"].append(str(mission_id))
            status = str(status)
            if status == "completed":
                rec["completed"] += 1
                if int(attempts or 0) <= 1:
                    rec["first_attempt_ok"] += 1
            elif status == "blocked":
                rec["blocked"] += 1
            elif status == "failed":
                rec["failed"] += 1
            if int(attempts or 0) > 1:
                rec["rework"] += 1
            if status != "completed":
                from ahos.cognitive_memory import classify_cause

                rec["causes"][classify_cause(str(error or ""))] += 1
            rec["last_at"] = max(rec["last_at"], str(updated_at or ""))
    return stats


def _help_stats() -> dict[str, dict]:
    stats: dict[str, dict] = {}
    for row in _lines(RUNTIME / "cognition" / "_collective.jsonl"):
        if row.get("kind") != "handoff":
            continue
        for role, key in (("given", "from"), ("received", "to")):
            worker = str(row.get(key) or "")
            if not worker:
                continue
            rec = stats.setdefault(worker, {"given": 0, "received": 0})
            rec[role] += 1
    return stats


def _first_learning() -> dict[str, str]:
    first: dict[str, str] = {}
    for path in (RUNTIME / "learning").glob("*.jsonl"):
        for row in _lines(path):
            worker = str(row.get("worker") or "")
            at = str(row.get("at") or "")
            if worker and at and (worker not in first or at < first[worker]):
                first[worker] = at
    return first


def _evidence() -> dict[str, str]:
    out = {}
    for path in (RUNTIME / "cognition").glob("*.json"):
        if path.name.startswith(("_", ".")):
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        out[str(payload.get("worker_id"))] = str(
            (payload.get("evidence") or {}).get("status") or "")
    return out


def _learning_impact(mission_stats: dict[str, dict], first_learning: dict[str, str]) -> dict:
    """İlk öğrenme kaydından önce/sonra görev başarısı; yalnız yeterli örnekte."""

    impact = {}
    if not DB.is_file():
        return impact
    with sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True) as con:
        rows = con.execute(
            "select mission_id, status, updated_at, result_json from missions "
            "where result_json is not null").fetchall()
    by_worker: dict[str, list[tuple[str, str]]] = {}
    for mission_id, status, updated_at, raw in rows:
        try:
            payload = json.loads(raw)
        except TypeError:
            continue
        for step in payload.get("steps") or []:
            worker = step.get("worker_id")
            if worker:
                by_worker.setdefault(str(worker), []).append(
                    (str(updated_at or ""), str(status)))
    for worker, items in by_worker.items():
        cutoff = first_learning.get(worker)
        if not cutoff:
            impact[worker] = {"before": None, "after": None,
                              "note": "no learning record"}
            continue
        before = [status for at, status in items if at < cutoff]
        after = [status for at, status in items if at >= cutoff]
        if len(before) < 3 or len(after) < 3:
            impact[worker] = {"before": len(before), "after": len(after),
                              "note": "insufficient sample (<3)"}
            continue
        b = round(sum(1 for s in before if s == "completed") / len(before), 3)
        a = round(sum(1 for s in after if s == "completed") / len(after), 3)
        impact[worker] = {"before": b, "after": a, "delta": round(a - b, 3),
                          "n_before": len(before), "n_after": len(after),
                          "note": "measured from mission outcomes"}
    return impact


def build(*, learning_impact: bool = False) -> dict:
    metrics = _metrics_rows()
    missions = _mission_stats()
    help_stats = _help_stats()
    evidence = _evidence()
    workers = sorted(set(metrics) | set(missions) | set(evidence))
    rows = []
    for worker in workers:
        m = metrics.get(worker) or {}
        s = missions.get(worker) or {}
        h = help_stats.get(worker) or {}
        attempts_base = max(1, int(s.get("missions") or 0))
        row = {
            "worker": worker,
            "runs": int(m.get("runs") or 0),
            "run_success_rate": round(int(m.get("success") or 0) / max(1, int(m.get("runs") or 0)), 3)
            if m.get("runs") else None,
            "avg_duration_ms": round(float(m.get("duration_ms") or 0) / max(1, int(m.get("runs") or 0)), 1)
            if m.get("runs") else None,
            "missions": int(s.get("missions") or 0),
            "final_qa_rate": round(int(s.get("completed") or 0) / attempts_base, 3)
            if s.get("missions") else None,
            "first_attempt_success": round(int(s.get("first_attempt_ok") or 0) / attempts_base, 3)
            if s.get("missions") else None,
            "rework": int(s.get("rework") or 0),
            "error_repeat_rate": round(min(1.0, max((s.get("causes") or Counter()).values())
                                           / max(1, (s.get("blocked") or 0) + (s.get("failed") or 0))), 3)
            if (s.get("blocked") or 0) + (s.get("failed") or 0) else None,
            "help_given": int(h.get("given") or 0),
            "help_received": int(h.get("received") or 0),
            "evidence": evidence.get(worker, "no_profile"),
            "cost_usd": None,  # işçi bazında atfedilmiş maliyet kaydı yok
            "resource_note": "cost not attributed per worker",
            "last_at": max(str(m.get("last_at") or ""), str(s.get("last_at") or "")),
        }
        rows.append(row)
    payload = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "schema": "ahos.skill-metrics.v1",
        "workers": len(rows),
        "with_runs": sum(1 for row in rows if row["runs"]),
        "with_missions": sum(1 for row in rows if row["missions"]),
        "note": "null = insufficient data; no fabricated improvement",
        "rows": rows,
    }
    if learning_impact:
        payload["learning_impact"] = _learning_impact(missions, _first_learning())
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--learning-impact", action="store_true")
    args = parser.parse_args(argv)
    payload = build(learning_impact=args.learning_impact)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"workers": payload["workers"],
                      "with_runs": payload["with_runs"],
                      "with_missions": payload["with_missions"],
                      "learning_impact": len(payload.get("learning_impact") or {}),
                      "report": str(REPORT)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
