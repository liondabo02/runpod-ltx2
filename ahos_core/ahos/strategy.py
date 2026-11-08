"""Strateji katmanı — zihin kendi geçmişinden kendini ayarlar."""

from __future__ import annotations

import time


def apply(mind) -> dict:
    """Son olaylara bakıp stratejiyi günceller ve zihne yazar."""

    # Score real mission executions only. A thought, chat or scheduled
    # status update is not evidence that an agent succeeded at work.
    recent = [e for e in mind.events[-30:]
              if e.get("kind") == "mission" and isinstance(e.get("ok"), bool)]
    kinds: dict = {}
    for event in recent:
        key = str(event.get("plan_type") or "mission")
        record = kinds.setdefault(key, {"ok": 0, "fail": 0})
        record["ok" if event["ok"] else "fail"] += 1

    total = sum(v["ok"] + v["fail"] for v in kinds.values()) or 1
    rate = round(sum(v["ok"] for v in kinds.values()) / total, 3)
    best = max(kinds.items(), key=lambda kv: kv[1]["ok"])[0] if kinds else "verified_mission_missing"
    worst = max(kinds.items(), key=lambda kv: kv[1]["fail"])[0] if kinds else ""

    strategy = {
        "rate": rate,
        "best_action": best,
        "avoid": worst if kinds.get(worst, {}).get("fail", 0) > 0 else "",
        "risk_tolerance": round(0.3 + rate * 0.5, 2),
        "plan_depth": 3 if rate >= 0.8 else (4 if rate >= 0.5 else 5),
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }

    mind.self_model = dict(mind.self_model or {})
    previous = dict(mind.self_model.get("strategy") or {})
    if previous.get("preferred_plan"):
        strategy["preferred_plan"] = previous["preferred_plan"]
    mind.self_model["strategy"] = strategy
    mind.self_model["strategy_history"] = (
        list(mind.self_model.get("strategy_history") or []) + [strategy]
    )[-10:]
    return strategy
