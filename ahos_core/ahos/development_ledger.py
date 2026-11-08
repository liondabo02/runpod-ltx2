"""Gelisim defteri: her iscinin once/sonra durumu (gercek sayilar)."""
import json, time
from pathlib import Path


def build(runtime_dir) -> dict:
    runtime = Path(runtime_dir)
    minds_dir = runtime / "minds"
    rows = []
    for f in minds_dir.glob("*.json"):
        if f.name.startswith("_"):
            continue
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        m = d.get("self_model") or {}
        hist = m.get("strategy_history") or []
        rows.append({
            "worker": d.get("worker_id"),
            "department": d.get("department"),
            "events": len(d.get("events") or []),
            "success_rate": round(float(m.get("success_rate") or 0) * 100, 1),
            "strategy_versions": len(hist),
            "last_strategy": hist[-1] if hist else {},
            "plan_scores": m.get("plan_scores") or {},
            "preferred_plan": m.get("preferred_plan") or "",
        })
    rows.sort(key=lambda r: (-r["events"], r["worker"] or ""))
    dept = {}
    for r in rows:
        d = r["department"] or "?"
        rec = dept.setdefault(d, {"workers": 0, "events": 0, "rate_sum": 0.0})
        rec["workers"] += 1
        rec["events"] += r["events"]
        rec["rate_sum"] += r["success_rate"]
    for d, rec in dept.items():
        rec["avg_rate"] = round(rec.pop("rate_sum") / max(1, rec["workers"]), 1)

    out = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "workers": len(rows),
        "total_events": sum(r["events"] for r in rows),
        "avg_events": round(sum(r["events"] for r in rows) / max(1, len(rows)), 1),
        "with_plan_score": sum(1 for r in rows if r["plan_scores"]),
        "departments": dept,
        "top": rows[:15],
    }
    cfg = Path(runtime).parent / "config"
    cfg.mkdir(parents=True, exist_ok=True)
    (cfg / "development-ledger.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out