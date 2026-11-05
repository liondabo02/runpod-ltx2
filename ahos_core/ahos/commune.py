"""İşçiler arası konuşma — mesaj kutusu, soru-cevap ve ortak konuşma kaydı.

Gerçek bilinç değil; **ajanlar arası iletişim protokolü**:
- her işçi kendi zihnine dayanarak mesaj yazar (soru/durum/öneri)
- aynı departmandan veya benzer dersi olan işçi cevap verir
- konuşma runtime/minds/conversations.jsonl dosyasına yazılır
- departman beyni en sık geçen konuyu öğrenir
"""

from __future__ import annotations

import json
import random
import time
from pathlib import Path

from . import cognition
from .worker_mind import load, save


def _log(runtime: Path) -> Path:
    path = runtime / "minds" / "conversations.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _post(runtime: Path, sender: str, department: str, topic: str, body: str, reply_to: str = "") -> dict:
    message = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "from": sender,
        "department": department,
        "topic": topic,
        "body": body[:400],
        "reply_to": reply_to,
    }
    with open(_log(runtime), "a", encoding="utf-8") as handle:
        handle.write(json.dumps(message, ensure_ascii=False) + "\n")
    return message


def converse(runtime_dir, departments: list, rounds: int = 3, seed: int | None = None) -> dict:
    """Departman içi soru-cevap turları: işçiler birbirine yazar, cevap verir."""

    runtime = Path(runtime_dir)
    rng = random.Random(seed if seed is not None else int(time.time()))
    members: dict[str, list[str]] = {}
    for dep in departments:
        dep_id = str(dep.get("department_id") or "")
        members[dep_id] = [str(w.get("worker_id") or "") for w in dep.get("workers") or []]

    pairs = 0
    messages = 0
    for _ in range(rounds):
        for dep_id, worker_ids in members.items():
            if len(worker_ids) < 2:
                continue
            asker, responder = rng.sample(worker_ids, 2)
            asker_mind = load(runtime, asker, dep_id)
            responder_mind = load(runtime, responder, dep_id)

            topic = str((asker_mind.self_model or {}).get("goal") or "durum")
            question = (
                f"{dep_id} için hedefim '{topic}'. "
                f"Planım: {' → '.join((asker_mind.self_model or {}).get('plan') or ['plan yok'])}. "
                "Sende işe yarayan bir yöntem var mı?"
            )
            answer = str((responder_mind.self_model or {}).get("lesson") or "henüz dersim yok; birlikte deneyelim.")

            _post(runtime, asker, dep_id, topic, question)
            _post(runtime, responder, dep_id, topic, answer, reply_to=asker)

            cognition.learn_from(runtime, responder, dep_id, cognition.extract_lesson(
                {"from": asker, "body": question}), source="soru")
            cognition.learn_from(runtime, asker, dep_id, cognition.extract_lesson(
                {"from": responder, "body": answer}), source="cevap")
            for mind, text, kind in ((asker_mind, question, "ask"), (responder_mind, answer, "answer")):
                mind.events.append({
                    "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "kind": kind,
                    "detail": text[:300],
                    "ok": True,
                })
                save(runtime, mind)

            pairs += 1
            messages += 2

    return {"pairs": pairs, "messages": messages, "departments": len(members)}


def recent(runtime_dir, limit: int = 10) -> list[dict]:
    path = Path(runtime_dir) / "minds" / "conversations.jsonl"
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]
    out = []
    for line in lines:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out
