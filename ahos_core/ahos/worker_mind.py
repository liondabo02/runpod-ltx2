"""Worker mind — çalışanın duygusal ve biliysel durumunu takip eder.

- emotion(mind, ctx) -> dict
  · heartbeat.mood_from ile aynı formül; self_model["mood"] olarak sakla
  · mind (brain dict) güncellenir
"""

from __future__ import annotations

import json


def emotion(mind: dict, ctx: dict) -> dict:
    """Calışanın duygusal durumunu hesaplar ve mind'e kaydeder.

    Args:
        mind: Mevcut mind dict (worker brain'i)
        ctx: Bağlam dict (pending, failures, delivered, quality_rate, last_task vb.)

    Returns:
        Güncellenmiş mind dict (mood kaydedildi)
    """
    # Heartbeat.mood_from benzer formül: pending, failures, delivered, quality_rate üzerinden
    pending = int(ctx.get("pending") or 0)
    failures = int(ctx.get("failures") or 0)
    delivered = int(ctx.get("delivered") or 0)
    quality = float(ctx.get("quality_rate") or 0.0)

    # Mood hesaplama: heartbeat.mood_from benzetmesi
    # Yüksek engel (high barrier): failures > delivered => stres
    # Düşük engel (low barrier): failures <= delivered => motive
    if failures > delivered:
        mood = "stres"
    else:
        mood = "motive"

    # Mind'e mood kaydet (zaten varsa üzerine yazar, append yapmaz)
    mind["mood"] = mood
    
    return mind


def self_improve(mind: Mind) -> dict:
    """Zihin kendi gecmisinden strateji cikarir ve kendini gunceller."""
    recent = mind.events[-30:]
    kinds: dict = {}
    for e in recent:
        k = str(e.get("kind") or "?")
        rec = kinds.setdefault(k, {"ok": 0, "fail": 0})
        rec["ok" if e.get("ok") else "fail"] += 1

    total = sum(v["ok"] + v["fail"] for v in kinds.values()) or 1
    wins = sum(v["ok"] for v in kinds.values())
    rate = round(wins / total, 3)

    best = max(kinds.items(), key=lambda kv: kv[1]["ok"])[0] if kinds else "think"
    worst = max(kinds.items(), key=lambda kv: kv[1]["fail"])[0] if kinds else ""

    strategy = {
        "rate": rate,
        "best_action": best,
        "avoid": worst if worst and kinds.get(worst, {}).get("fail", 0) > 0 else "",
        "risk_tolerance": round(0.3 + rate * 0.5, 2),
        "plan_depth": 3 if rate >= 0.8 else (4 if rate >= 0.5 else 5),
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    mind.self_model = dict(mind.self_model or {})
    previous = mind.self_model.get("strategy") or {}
    mind.self_model["strategy"] = strategy
    mind.self_model["strategy_history"] = (list(mind.self_model.get("strategy_history") or []) + [strategy])[-10:]
    mind.events.append({
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "kind": "self_improve",
        "detail": f"strateji güncellendi: rate={rate} best={best} risk={strategy['risk_tolerance']}",
        "ok": True,
    })
    return {"strategy": strategy, "changed": strategy != previous}
