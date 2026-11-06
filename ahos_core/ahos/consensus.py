"""Oylama ve plan puanlama — departman içi kolektif karar + plan kalitesi.

vote(): aynı departmandaki işçiler seçenekleri kendi güven/başarılarına göre puanlar,
en yüksek toplu puanı alan seçenek kazanır ve konuşma kaydına "vote" olarak yazılır.

score_plan(): bir planın sonucunu (başarı, süre) zihne yazar; plan tipine göre
ortalama başarı hesaplanır ve stratejiye geri beslenir.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from .worker_mind import load, save


def _log(runtime: Path, record: dict) -> None:
    path = runtime / "minds" / "conversations.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def vote(runtime_dir, department: str, topic: str, options: list[str],
         workers: list[str] | None = None) -> dict:
    """İşçiler seçenekleri puanlar; en yüksek toplu puan kazanır."""

    runtime = Path(runtime_dir)
    roster = workers or []
    if not roster:
        dept_dir = runtime / "minds" / "departments" / f"{department}.json"
        if dept_dir.exists():
            try:
                roster = [l.get("worker") for l in json.loads(
                    dept_dir.read_text(encoding="utf-8")).get("lessons", []) if l.get("worker")]
            except (json.JSONDecodeError, OSError):
                roster = []
    if not roster:
        roster = [department + "-manager"]

    totals = {option: 0.0 for option in options}
    votes: list[dict] = []
    for wid in roster[:12]:
        mind = load(runtime, wid, department)
        model = mind.self_model or {}
        strategy = model.get("strategy") or {}
        conf = float(strategy.get("rate") or mind.success_rate or 0.5)
        for option in options:
            # basit tercih: kısa ve "engel/kuyruk" içeren seçenek daha çok puan
            bias = 0.0
            low = option.lower()
            if "engel" in low: bias += 0.15
            if "kuyruk" in low: bias += 0.10
            if len(option) > 80: bias -= 0.10
            totals[option] += (conf + bias)
        votes.append({"worker": wid, "confidence": round(conf, 3)})

    winner = max(totals, key=totals.get)
    record = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "kind": "vote",
        "from": department,
        "department": department,
        "topic": topic,
        "body": f"oylama: {len(roster)} işçi · kazanan: {winner}",
        "totals": {k: round(v, 2) for k, v in totals.items()},
        "winner": winner,
        "votes": votes,
    }
    _log(runtime, record)
    return {"winner": winner, "totals": record["totals"], "voters": len(votes)}


def score_plan(runtime_dir, worker_id: str, department: str, plan_type: str,
               ok: bool, duration_s: float = 0.0) -> dict:
    """Plan sonucunu zihne yaz; plan tipine göre ortalama başarı güncellenir."""

    runtime = Path(runtime_dir)
    mind = load(runtime, worker_id, department)
    model = dict(mind.self_model or {})
    scores = dict(model.get("plan_scores") or {})
    entry = scores.get(plan_type) or {"ok": 0, "fail": 0, "total_s": 0.0}
    entry["ok" if ok else "fail"] += 1
    entry["total_s"] = round(float(entry.get("total_s") or 0.0) + duration_s, 2)
    scores[plan_type] = entry
    model["plan_scores"] = scores

    best = max(scores.items(), key=lambda kv: kv[1]["ok"] / max(1, kv[1]["ok"] + kv[1]["fail"]))
    model["best_plan_type"] = best[0]
    model["strategy"] = dict(model.get("strategy") or {})
    model["strategy"]["preferred_plan"] = best[0]
    mind.self_model = model
    save(runtime, mind)
    rate = round(entry["ok"] / max(1, entry["ok"] + entry["fail"]), 3)
    return {"plan_type": plan_type, "rate": rate, "best": best[0]}
