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
import sqlite3
import time
from pathlib import Path


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


def _latest_department_result(runtime: Path, department: str) -> dict | None:
    """Read one actual terminal mission; do not fabricate worker ownership."""
    database = runtime / "company-service.db"
    if not database.is_file():
        return None
    try:
        with sqlite3.connect("file:" + database.as_posix() + "?mode=ro", uri=True) as con:
            row = con.execute(
                "select mission_id, objective, status, last_error, updated_at "
                "from missions where primary_department=? "
                "and status in ('completed','blocked','failed') "
                "order by updated_at desc limit 1",
                (department,),
            ).fetchone()
    except (sqlite3.Error, OSError):
        return None
    if row is None:
        return None
    return {
        "id": str(row[0] or ""),
        "objective": str(row[1] or "")[:130],
        "status": str(row[2] or ""),
        "error": str(row[3] or "")[:110],
        "updated_at": str(row[4] or ""),
    }


def converse(runtime_dir, departments: list, rounds: int = 3, seed: int | None = None) -> dict:
    """Share verifiable department results; conversation is not model learning."""

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
            record = _latest_department_result(runtime, dep_id)
            if record:
                topic = record["id"]
                question = (
                    f"{dep_id} departmanı gerçek kuyruk kaydı {record['id']} "
                    f"({record['status']}, {record['updated_at']}): "
                    f"{record['objective']}. Bu sonucu nasıl doğrulamalıyız?"
                )
                if record["status"] == "completed":
                    advice = "Tamamlandı kaydı var; bağımsız teslim/QA kanıtını denetleyelim."
                else:
                    advice = (
                        f"Engel nedeni: {record['error'] or 'kayıtta gerekçe yok'}. "
                        "Önce sebebi ve önceki yan etkileri doğrulayalım; kör tekrar yok."
                    )
                answer = f"{record['id']} için veritabanı durumu {record['status']}. {advice}"
            else:
                topic = "kayıt yok"
                question = f"{dep_id} için doğrulanmış tamamlanmış/engelli görev kaydı bulunamadı."
                answer = "Gerçek görev kaydı olmadan çalıştım ya da öğrendim diyemem."

            _post(runtime, asker, dep_id, topic, question)
            _post(runtime, responder, dep_id, topic, answer, reply_to=asker)
            # This read-only exchange is a status summary, not a model-based
            # inference or a verified worker result. It must not inflate mind
            # success rates or create fabricated 'lessons'.

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
