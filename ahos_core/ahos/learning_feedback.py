"""Öğrenme geribildirleme – hangi ders kartlarının 'karara' etkili olduğunu belirler.

- weights(runtime, cards) → runtime/learning/weights.json
  {kart_id: {weight: float, wins: int, losses: int}}
- top_cards(runtime, n=3) → en yüksek ağırlıklı 3 kart metni
- apply_to_prompt(runtime, prompt) → prompt + "\n\n### Öğrenilen dersler" + top_cards
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from .self_learning import _book as _load_departments
from .knowledge import search as _knowledge_search


def weights(runtime_dir: str | Path, cards: list[dict]) -> dict:
    """Kart ağırlıklarını hesapla: wins - losses çarpımı * freshlik faktörü.

    Args:
        runtime_dir: runtime dizini
        cards: DepartmentCourse.questions/results verisi

    Returns:
        {kart_id: {weight: float, wins: int, losses: int}}
    """
    runtime = Path(runtime_dir)
    wpath = runtime / "learning" / "weights.json"
    wpath.parent.mkdir(parents=True, exist_ok=True)

    # Eski ağırlıkları yükle (var ise)
    old: dict = {}
    if wpath.exists():
        try:
            old = json.loads(wpath.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            old = {}

    result: dict = {}
    now = time.time()

    for card in cards:
        cid = str(card.get("id") or card.get("course_id") or "unknown")
        # wins/losses: passed/failed bilgisinden
        passed = int(card.get("passed", 0))
        total = int(card.get("total", card.get("questions", 1) or 1))
        lost = max(0, total - passed)

        # Freshlik: son okunma zamana göre azalıyor
        age_factor = max(0.1, 1.0 - (now - card.get("last_seen", now)) / (7 * 86400))

        w = round(max(0.01, (passed - lost) * age_factor), 4)
        result[cid] = {"weight": w, "wins": passed, "losses": lost}

    # Eski kayıtları koru (yeni kartlar ekle, eskiyi silme)
    merged = {**old, **result}
    wpath.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def top_cards(runtime_dir: str | Path, n: int = 3) -> list[dict]:
    """Ağırlıklı en yüksek n kartı döndür.

    Args:
        runtime_dir: runtime dizini
        n: kaç kart alınacak

    Returns:
        [{id, weight, wins, losses, text}, ...]
    """
    runtime = Path(runtime_dir)
    wpath = runtime / "learning" / "weights.json"

    if not wpath.exists():
        return []

    try:
        w = json.loads(wpath.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    # score'a göre sırala, descending
    sorted_items = sorted(w.items(), key=lambda item: item[1].get("weight", 0), reverse=True)
    top = sorted_items[:n]

    result: list[dict] = []
    for cid, data in top:
        # Kart metnini knowledge index'inden çek
        try:
            kb = _knowledge_search(runtime, cid, limit=1)
            text = kb[0]["text"] if kb else cid
        except Exception:
            text = cid
        result.append({
            "id": cid,
            "weight": data.get("weight", 0),
            "wins": data.get("wins", 0),
            "losses": data.get("losses", 0),
            "text": text,
        })

    return result


def apply_to_prompt(runtime_dir: str | Path, prompt: str) -> str:
    """Prompt üzerine en yüksek ağırlıklı 3 öğrenilen kartı ekler."""
    runtime = Path(runtime_dir)
    cards = top_cards(runtime, n=3)
    if not cards:
        return prompt

    lines = ["### Öğrenilen dersler"]
    for c in cards:
        lines.append(f"- {c['id']}: weight={c['weight']}, wins={c['wins']}, losses={c['losses']}")
        lines.append(c.get("text", "")[:200])
    enriched = prompt + "\n\n" + "\n".join(lines)
    return enriched
