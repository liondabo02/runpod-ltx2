"""Bilis katmani: ongoru, mantik yurutme, konusmadan ogrenme."""
from __future__ import annotations

import json
import time
from pathlib import Path


def predict(ctx: dict, mind) -> dict:
    completed = int(ctx.get("completed", 0))
    pending = int(ctx.get("pending", 0))
    blocked = int(ctx.get("blocked", 0))
    history = list((mind.self_model or {}).get("queue_history") or [])
    history.append({"completed": completed, "pending": pending, "blocked": blocked})
    history = history[-10:]
    if len(history) >= 2:
        throughput = history[-1]["completed"] - history[-2]["completed"]
        growth = history[-1]["pending"] - history[-2]["pending"]
    else:
        throughput, growth = 0, 0
    risk = "low"
    if blocked > completed * 0.25 and blocked > 50:
        risk = "high"
    elif blocked > 100 or growth > 50:
        risk = "medium"
    eta = round(pending / max(throughput, 1), 1) if pending and throughput > 0 else None
    forecast = {"throughput_per_tick": throughput, "pending_growth": growth, "risk": risk,
                "eta_ticks": eta, "next_focus": "engel" if risk != "low" else ("kuyruk" if pending > 8 else "gelisim")}
    mind.self_model = dict(mind.self_model or {})
    mind.self_model["queue_history"] = history
    mind.self_model["forecast"] = forecast
    return forecast


def reason(goal: str, facts: dict) -> list:
    steps = []
    blocked = int(facts.get("blocked", 0))
    pending = int(facts.get("pending", 0))
    rate = float(facts.get("rate", 0))
    if blocked > 100:
        steps.append(f"engel {blocked} > 100 -> once engel tasfiyesi gerekli")
    if pending > 50:
        steps.append(f"bekleyen {pending} > 50 -> teslim hizi artirilmali")
    if rate and rate < 0.7:
        steps.append(f"basari %{round(rate * 100)} < 70 -> kapsam daraltilmali")
    if "engel" in goal and blocked <= 100:
        steps.append("engel hedefi guncelligini yitirdi -> yeni hedef sec")
    if not steps:
        steps.append("kritik olgu yok -> mevcut plan gecerli")
    return steps


def learn_from(runtime_dir, worker_id: str, department: str, lesson: str, source: str = "konusma") -> None:
    from .worker_mind import load, save

    runtime = Path(runtime_dir)
    mind = load(runtime, worker_id, department)
    mind.events.append({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "kind": f"learn:{source}",
                        "detail": lesson[:300], "ok": True})
    save(runtime, mind)


def extract_lesson(message: dict) -> str:
    body = str(message.get("body") or "").strip()
    sender = str(message.get("from") or "")
    return f"{sender} dedi: {body[:160]}" if body else ""


def simulate(goal: str, steps: list, facts: dict) -> dict:
    """Plani adim adim benzetimler; her adim icin beklenen durumu dondurur."""
    outcome = []
    blocked = int(facts.get("blocked", 0))
    for i, step in enumerate(steps or []):
        ok = True
        note = "uygulanabilir"
        if "engel" in str(step) and blocked == 0:
            ok = False
            note = "engel yok; bu adim gereksiz"
        outcome.append({"step": i + 1, "action": step, "ok": ok, "note": note})
    return {"goal": goal, "steps": outcome, "feasible": all(s["ok"] for s in outcome)}

def plan_from_goal(goal: str) -> list[dict[str, str]]:
    """Create a proposed plan; never claim that planned steps were executed."""
    goal = goal.strip()
    if not goal:
        raise ValueError("Hedef boş olamaz")
    return [
        {"action": f"analyze: {goal}", "status": "planned"},
        {"action": f"plan: {goal}", "status": "planned"},
        {"action": f"execute: {goal}", "status": "planned"},
    ]
