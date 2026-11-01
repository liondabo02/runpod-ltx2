"""Ajan kontrol katmanı — Munder Difflin + AgentSpace desenleri.

1. **Bilet anahtarı (ticket key)**: her göreve `PRJ-123` biçiminde kısa bir anahtar
   verilir; ajanlar ve panel aynı anahtarla konuşur.
2. **Devre kesici (circuit breaker)**: üst üste hata yapan ajan önce **yönlendirilir**
   (steer: küçük görev), sonra **kısıtlanır** (constrain: tek dosya), sonra
   **durdurulur** (stop). Munder Difflin'in "steer → constrain → stop" merdiveni.
3. **Bellek sarayı (memory palace lite)**: ajanın kalıcı notları markdown olarak
   tutulur, anahtar kelimeyle aranır (semantik dizin olmadan da çalışır).
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path

# ------------------------------- biletler -------------------------------


def ticket_prefix(project: str) -> str:
    """Proje adından 2-4 harflik anahtar üretir (ör. mipiluna → MIP)."""

    letters = re.sub(r"[^A-Za-zÇĞİÖŞÜçğıöşü]", "", project or "")
    if not letters:
        return "AHOS"
    return letters[:3].upper()


def ticket_key(project: str, sequence: int) -> str:
    return f"{ticket_prefix(project)}-{max(1, int(sequence))}"


def assign_ticket(runtime_dir: str | Path, mission_id: str, project: str) -> str:
    """Göreve bilet anahtarı atar ve kaydeder (idempotent)."""

    runtime = Path(runtime_dir)
    path = runtime / "tickets.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {"next": 1, "tickets": {}}

    existing = payload["tickets"].get(mission_id)
    if existing:
        return existing

    sequence = int(payload.get("next", 1))
    key = ticket_key(project, sequence)
    payload["tickets"][mission_id] = key
    payload["next"] = sequence + 1
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return key


def ticket_for(runtime_dir: str | Path, mission_id: str) -> str:
    try:
        payload = json.loads((Path(runtime_dir) / "tickets.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    return str((payload.get("tickets") or {}).get(mission_id) or "")


# ---------------------------- devre kesici ----------------------------

STEER_AT = 2
CONSTRAIN_AT = 3
STOP_AT = 4


@dataclass(frozen=True)
class BreakerDecision:
    action: str      # "ok" | "steer" | "constrain" | "stop"
    streak: int
    reason: str


def breaker(runtime_dir: str | Path, worker: str, *, success: bool | None = None) -> BreakerDecision:
    """Ajanın ardışık hata serisine göre karar verir; `success` verilirse kaydeder."""

    runtime = Path(runtime_dir)
    path = runtime / "breaker.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}

    state = payload.setdefault(worker, {"streak": 0, "updated": ""})
    if success is True:
        state["streak"] = 0
    elif success is False:
        state["streak"] = int(state.get("streak", 0)) + 1
        state["updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    streak = int(state.get("streak", 0))

    if success is not None:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    if streak >= STOP_AT:
        return BreakerDecision("stop", streak, f"{streak} ardışık hata: ajan durduruldu")
    if streak >= CONSTRAIN_AT:
        return BreakerDecision("constrain", streak, f"{streak} ardışık hata: tek dosya/küçük görev")
    if streak >= STEER_AT:
        return BreakerDecision("steer", streak, f"{streak} ardışık hata: görev küçültülmeli")
    return BreakerDecision("ok", streak, "")


def reset_breaker(runtime_dir: str | Path, worker: str) -> None:
    runtime = Path(runtime_dir)
    path = runtime / "breaker.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}
    payload[worker] = {"streak": 0, "updated": time.strftime("%Y-%m-%dT%H:%M:%S")}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------- bellek sarayı ----------------------------


def remember(runtime_dir: str | Path, actor: str, note: str) -> Path:
    """Ajanın kalıcı notunu yazar (markdown, aranabilir)."""

    directory = Path(runtime_dir) / "memory"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{actor}.md"
    stamp = time.strftime("%Y-%m-%d %H:%M")
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"\n## {stamp}\n{note.strip()}\n")
    return path


def recall(runtime_dir: str | Path, query: str, *, limit: int = 5) -> list[dict]:
    """Tüm ajan notlarında anahtar kelime araması yapar."""

    directory = Path(runtime_dir) / "memory"
    if not directory.exists():
        return []
    words = [word.casefold() for word in re.findall(r"\w{3,}", query or "")]
    hits: list[dict] = []
    for path in directory.glob("*.md"):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        score = sum(text.casefold().count(word) for word in words) if words else 0
        if score:
            hits.append({"actor": path.stem, "score": score, "excerpt": text[-400:]})
    hits.sort(key=lambda item: -item["score"])
    return hits[:limit]
