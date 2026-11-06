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


def _post(runtime: Path, sender: str, department: str, topic: str, body: str, reply_to: str = "", *, mission_id: str = "") -> dict:
    message = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "from": sender,
        "department": department,
        "topic": topic,
        "body": body[:400],
        "reply_to": reply_to,
    }
    if mission_id:
        message["mission_id"] = mission_id
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


def _latest_worker_results(
    runtime: Path, department: str, worker_ids: list[str]
) -> dict[str, dict]:
    """Find each worker's latest observed mission, using persisted step owners.

    A matching department or manager alone is not evidence that a worker did
    the work. The read-only query never invents ownership for missing results.
    """
    database = runtime / "company-service.db"
    wanted = set(worker_ids)
    if not database.is_file() or not wanted:
        return {}

    latest: dict[str, dict] = {}
    try:
        with sqlite3.connect("file:" + database.as_posix() + "?mode=ro", uri=True) as con:
            rows = con.execute(
                "select mission_id, objective, status, last_error, updated_at, result_json "
                "from missions where primary_department=? "
                "and status in ('completed','blocked','failed') and result_json is not null "
                "order by updated_at desc, rowid desc",
                (department,),
            )
            for mission_id, objective, status, error, updated_at, raw in rows:
                try:
                    payload = json.loads(raw)
                except (ValueError, TypeError):
                    continue
                if not isinstance(payload, dict) or not isinstance(payload.get("steps"), list):
                    continue
                for step in payload["steps"]:
                    if not isinstance(step, dict):
                        continue
                    worker = step.get("worker_id")
                    if (not isinstance(worker, str) or worker not in wanted
                            or worker in latest or step.get("worker_summary") is None):
                        continue
                    latest[worker] = {
                        "id": str(mission_id or ""),
                        "objective": str(objective or "")[:100],
                        "status": str(status or ""),
                        "error": str(error or "")[:110],
                        "updated_at": str(updated_at or ""),
                    }
                if len(latest) == len(wanted):
                    break
    except (sqlite3.Error, OSError):
        return {}
    return latest


def _mission_excerpt(record: dict, *, worker_owned: bool) -> str:
    ownership = "Son görevim" if worker_owned else "Departmanın son kayıtlı görevi (bana ait olduğu doğrulanmadı)"
    return (
        f"{ownership}: mission_id={record['id']} "
        f"objective={record['objective'][:100]}"
        f" (durum={record['status']})"
    )


def converse(runtime_dir, departments: list, rounds: int = 3, seed: int | None = None) -> dict:
    """Share verifiable department results; conversation is not model learning."""

    runtime = Path(runtime_dir)
    from_runtime_book = not departments
    cadence_file = runtime / "minds" / ".commune-cadence.json"
    cursor = 0
    if from_runtime_book:
        # The daemon may pass []. Rotate a few departments per interval
        # rather than producing a chat flood or staying silent forever.
        try:
            state = json.loads(cadence_file.read_text(encoding="utf-8"))
            if time.time() - float(state.get("last_at", 0)) < 900:
                return {"pairs": 0, "messages": 0, "departments": 0,
                        "reason": "cooldown"}
            cursor = int(state.get("next", 0))
        except (OSError, ValueError, TypeError, AttributeError):
            cursor = 0
        try:
            payload = json.loads((runtime / "departments.json").read_text(encoding="utf-8"))
            complete = payload.get("departments", []) if isinstance(payload, dict) else payload
            complete = [dep for dep in complete if isinstance(dep, dict)]
            if complete:
                take = min(4, len(complete))
                departments = [complete[(cursor + i) % len(complete)]
                               for i in range(take)]
                cursor = (cursor + take) % len(complete)
        except (OSError, ValueError, TypeError):
            departments = []
    rng = random.Random(seed if seed is not None else int(time.time()))
    members: dict[str, list[str]] = {}
    for dep in departments:
        dep_id = str(dep.get("department_id") or "")
        members[dep_id] = [str(w.get("worker_id") or "") for w in dep.get("workers") or []]

    # Load evidence once per department: every message can now name an observed
    # worker mission rather than attributing a random department task to them.
    worker_results = {
        dep_id: _latest_worker_results(runtime, dep_id, worker_ids)
        for dep_id, worker_ids in members.items()
    }
    department_results = {
        dep_id: _latest_department_result(runtime, dep_id)
        for dep_id in members
    }

    pairs = 0
    messages = 0
    for _ in range(rounds):
        for dep_id, worker_ids in members.items():
            if len(worker_ids) < 2:
                continue
            owned = worker_results[dep_id]
            # Choose a worker with a recorded step whenever one exists;
            # do not claim the sampled worker performed another worker's task.
            attributed = [wid for wid in worker_ids if wid in owned]
            asker = rng.choice(attributed or worker_ids)
            candidates = [wid for wid in worker_ids if wid != asker]
            proven_responders = [wid for wid in candidates if wid in owned]
            responder = rng.choice(proven_responders or candidates)

            asker_last = owned.get(asker)
            responder_last = owned.get(responder)
            reference = asker_last or responder_last or department_results[dep_id]
            if reference:
                topic = reference["id"]
                if asker_last:
                    question = (
                        _mission_excerpt(asker_last, worker_owned=True)
                        + ". Bu sonucu hangi bağımsız kanıtla doğrulayabiliriz?"
                    )
                else:
                    question = (
                        "Benim son görevim işçi bazında doğrulanamadı. "
                        + _mission_excerpt(reference, worker_owned=False)
                        + ". Bağımsız QA kanıtı var mı?"
                    )
                if reference["status"] == "completed":
                    advice = "Tamamlandı kaydı var; gerçek QA ve teslim kanıtını kontrol edelim."
                else:
                    advice = (
                        "Engel nedeni: "
                        + (reference["error"] or "kayıtta gerekçe yok")
                        + ". Kök nedeni kontrol edelim."
                    )
                if responder_last:
                    answer = (
                        _mission_excerpt(responder_last, worker_owned=True)
                        + ". " + advice
                    )
                else:
                    answer = (
                        "Bana ait son görev kaydı doğrulanamadı. Görüşülen "
                        f"mission_id={reference['id']} "
                        f"objective={reference['objective'][:100]}. {advice}"
                    )
            else:
                topic = "kayıt yok"
                question = (
                    f"{dep_id} için işçi bazında veya departmanda gerçek "
                    "sonuçlanmış görev kaydı bulunamadı."
                )
                answer = (
                    "Gerçek görev kaydı olmadan bir görev yaptığımı "
                    "ya da öğrendiğimi iddia edemem."
                )

            _post(
                runtime, asker, dep_id, topic, question,
                mission_id=(asker_last or reference or {}).get("id", ""),
            )
            _post(
                runtime, responder, dep_id, topic, answer, reply_to=asker,
                mission_id=(responder_last or reference or {}).get("id", ""),
            )
            # Summaries only: no synthetic mind success/lessons.
            pairs += 1
            messages += 2

    if from_runtime_book and members:
        cadence_file.parent.mkdir(parents=True, exist_ok=True)
        cadence_file.write_text(json.dumps({
            "last_at": time.time(), "next": cursor,
            "department_count": len(members),
        }), encoding="utf-8")
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
