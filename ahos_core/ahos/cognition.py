"""Biliş katmanı — öngörü, mantık yürütme ve konuşmadan öğrenme.

- predict(ctx, mind)  : kuyruğun bir sonraki durumunu ve riski tahmin eder
- reason(goal, facts) : kural tabanlı çıkarım zinciri (if-then)
- learn_from(runtime, worker, lesson) : konuşmadan çıkan dersi zihne yazar
"""

from __future__ import annotations

import json
import time
from pathlib import Path



def predict(ctx: dict, mind) -> dict:
    """Kuyruk eğilimi + risk tahmini (geçmişe dayalı, model gerekmez)."""

    completed = int(ctx.get("completed", 0))
    pending = int(ctx.get("pending", 0))
    blocked = int(ctx.get("blocked", 0))

    history = list((mind.self_model or {}).get("queue_history") or [])
    history.append({"completed": completed, "pending": pending, "blocked": blocked})
    history = history[-10:]

    if len(history) >= 2:
        prev, cur = history[-2], history[-1]
        throughput = cur["completed"] - prev["completed"]
        growth = cur["pending"] - prev["pending"]
    else:
        throughput, growth = 0, 0

    risk = "low"
    if blocked > completed * 0.25 and blocked > 50:
        risk = "high"
    elif blocked > 100 or growth > 50:
        risk = "medium"

    eta_minutes = None
    if pending and throughput > 0:
        eta_minutes = round(pending / max(throughput, 1), 1)

    forecast = {
        "throughput_per_tick": throughput,
        "pending_growth": growth,
        "risk": risk,
        "eta_ticks": eta_minutes,
        "next_focus": "engel" if risk != "low" else ("kuyruk" if pending > 8 else "gelişim"),
    }
    mind.self_model = dict(mind.self_model or {})
    mind.self_model["queue_history"] = history
    mind.self_model["forecast"] = forecast
    return forecast


def reason(goal: str, facts: dict) -> list[str]:
    """Kural tabanlı mantık zinciri: verilen olgulardan çıkarımlar üretir."""

    steps: list[str] = []
    blocked = int(facts.get("blocked", 0))
    pending = int(facts.get("pending", 0))
    rate = float(facts.get("rate", 0))

    if blocked > 100:
        steps.append(f"engel {blocked} > 100 → önce engel tasfiyesi gerekli")
    if pending > 50:
        steps.append(f"bekleyen {pending} > 50 → teslim hızı artırılmalı")
    if rate and rate < 0.7:
        steps.append(f"başarı %{round(rate * 100)} < 70 → kapsam daraltılmalı")
    if "engel" in goal and blocked <= 100:
        steps.append("engel hedefi güncelliğini yitirdi → yeni hedef seç")
    if not steps:
        steps.append("kritik olgu yok → mevcut plan geçerli")
    return steps


def learn_from(runtime_dir, worker_id: str, department: str, lesson: str, source: str = "konuşma") -> None:
    """Konuşmadan çıkan dersi zihne olay olarak yaz."""

    from .worker_mind import load, save

    runtime = Path(runtime_dir)
    mind = load(runtime, worker_id, department)
    mind.events.append({
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "kind": f"learn:{source}",
        "detail": lesson[:300],
        "ok": True,
    })
    save(runtime, mind)


def extract_lesson(message: dict) -> str:
    """Mesajdan öğrenilebilir ders çıkarır."""

    body = str(message.get("body") or "").strip()
    sender = str(message.get("from") or "")
    if not body:
        return ""
    return f"{sender} dedi: {body[:160]}"
