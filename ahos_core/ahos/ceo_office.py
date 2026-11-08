"""CEO ofisi: gerçek bir CEO'nun yaptığı işlerin ölçülebilir çekirdeği.

Dört yetki:

1. **Hedef koy** (`set_goal`) — sahibin hedefini kaydeder, departmanlara böler,
   her parça için kuyruğa görev bırakır.
2. **Günlük brifing** (`daily_brief`) — gerçek sayılar: teslim, engel, en sık
   neden, en zayıf departman, sıradaki 3 aksiyon.
3. **Değerlendirme** (`review`) — işçi karnelerini okur, en zayıf departmana
   iyileştirme görevi açar, kararı gerekçesiyle kaydeder.
4. **Karar kaydı** (`decide`) — soruyu kanıtla yanıtlar, kararı ve gerekçeyi
   `runtime/ceo/decisions.jsonl` dosyasına yazar.

Tüm çıktılar dosyaya yazılır; model çağrısı yoktur (deterministik, hızlı).
"""

from __future__ import annotations

import json
import sqlite3
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path


def _ceo_dir(runtime: Path) -> Path:
    path = runtime / "ceo"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _queue_stats(runtime: Path) -> dict[str, int]:
    db = runtime / "company-service.db"
    if not db.exists():
        return {}
    try:
        with sqlite3.connect(db) as con:
            return dict(con.execute("select status, count(*) from missions group by status").fetchall())
    except sqlite3.Error:
        return {}


def _worker_stats(runtime: Path, limit: int = 4000) -> dict[str, tuple[int, int]]:
    ledger = runtime / "worker-metrics.jsonl"
    stats: dict[str, list[int]] = {}
    if not ledger.exists():
        return {}
    for line in ledger.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        worker = str(row.get("worker_id") or "?")
        item = stats.setdefault(worker, [0, 0])
        item[0] += 1
        item[1] += 1 if row.get("success") else 0
    return {key: (runs, ok) for key, (runs, ok) in stats.items()}


def _blocked_causes(runtime: Path, limit: int = 200) -> Counter:
    db = runtime / "company-service.db"
    causes: Counter = Counter()
    if not db.exists():
        return causes
    try:
        from .failure_analytics import classify_error

        with sqlite3.connect(db) as con:
            rows = con.execute(
                "select last_error from missions where status='blocked' order by updated_at desc limit ?",
                (limit,),
            ).fetchall()
        for (error,) in rows:
            causes[classify_error({"message": error or ""})] += 1
    except Exception:  # noqa: BLE001 - sınıflandırma isteğe bağlı
        pass
    return causes


def _enqueue(runtime: Path, mission_id: str, objective: str, department: str) -> bool:
    try:
        from .autonomous_company import PersistentMissionQueue

        queue = PersistentMissionQueue(runtime / "company-service.db")
        queue.enqueue(
            mission_id=mission_id,
            objective=objective,
            primary_department=department,
            max_attempts=1,
            replace_existing=True,
        )
        return True
    except Exception:  # noqa: BLE001 - kuyruk isteğe bağlı
        return False


@dataclass
class Brief:
    delivery_rate: float
    completed: int
    blocked: int
    pending: int
    weakest_department: str
    top_causes: tuple[str, ...]
    actions: tuple[str, ...] = field(default_factory=tuple)

    def text(self) -> str:
        lines = [
            f"teslim %{round(self.delivery_rate * 100)} "
            f"({self.completed} tamam / {self.blocked} engel / {self.pending} bekleyen)",
            "en sık engel: " + (", ".join(self.top_causes[:3]) or "yok"),
            f"en zayıf departman: {self.weakest_department or '-'}",
        ]
        if self.actions:
            lines.append("sıradaki aksiyonlar:")
            lines += [f"- {item}" for item in self.actions]
        return "\n".join(lines)


def daily_brief(runtime_dir: str | Path) -> Brief:
    """Gerçek sayılardan yönetici özeti üretir."""

    runtime = Path(runtime_dir)
    counts = _queue_stats(runtime)
    completed = counts.get("completed", 0)
    blocked = counts.get("blocked", 0)
    pending = counts.get("pending", 0)
    total = completed + blocked + pending
    rate = completed / total if total else 0.0

    worker_stats = _worker_stats(runtime)
    weakest = ""
    weakest_rate = 1.0
    for worker, (runs, ok) in worker_stats.items():
        if runs < 10:
            continue
        value = ok / runs
        if value < weakest_rate:
            weakest_rate = value
            weakest = f"{worker} (%{round(value * 100)}, {runs} koşu)"

    causes = _blocked_causes(runtime)
    top = tuple(cause for cause, _ in causes.most_common(3))

    actions: list[str] = []
    if pending:
        actions.append(f"{pending} bekleyen görevi işle (daemon/drain)")
    if blocked:
        actions.append(f"{blocked} engelli görevi sınıfa göre yeniden dene")
    if weakest:
        actions.append(f"zayıf halka için iyileştirme görevi aç: {weakest}")

    brief = Brief(
        delivery_rate=rate,
        completed=completed,
        blocked=blocked,
        pending=pending,
        weakest_department=weakest,
        top_causes=top,
        actions=tuple(actions),
    )
    (_ceo_dir(runtime) / "last-brief.json").write_text(
        json.dumps(
            {
                "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "delivery_rate": round(rate, 4),
                "completed": completed,
                "blocked": blocked,
                "pending": pending,
                "weakest": weakest,
                "top_causes": list(top),
                "actions": list(actions),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return brief


def set_goal(runtime_dir: str | Path, objective: str, departments: tuple[str, ...], owner: str = "sahip") -> dict:
    """Hedefi kaydeder ve her departmana bir parça bırakır."""

    runtime = Path(runtime_dir)
    stamp = int(time.time())
    goal_id = f"GOAL-{stamp}"
    created: list[str] = []
    for department in departments:
        mission_id = f"CMD-{department}-goal-{stamp}"
        part = f"{objective} — {department} payı: ölçülebilir tek adım üret"
        if _enqueue(runtime, mission_id, part, department):
            created.append(mission_id)

    record = {
        "goal_id": goal_id,
        "objective": objective,
        "departments": list(departments),
        "missions": created,
        "owner": owner,
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "status": "active" if created else "queued-failed",
    }
    path = _ceo_dir(runtime) / "goals.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def review(runtime_dir: str | Path, *, open_task: bool = False) -> dict:
    """Karneleri okur, en zayıf departmana iyileştirme görevi açar."""

    runtime = Path(runtime_dir)
    brief = daily_brief(runtime)
    stamp = int(time.time())
    decision = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "type": "review",
        "delivery_rate": round(brief.delivery_rate, 4),
        "weakest": brief.weakest_department,
        "actions": list(brief.actions),
    }
    mission = ""
    if open_task and brief.weakest_department:
        worker = brief.weakest_department.split(" ")[0]
        department = worker.split("-")[0]
        mission_id = f"CMD-{department}-ceo-review-{stamp}"
        objective = (
            f"Performans düşük: {worker}. Son 10 görevin hatasını çıkar, "
            "en sık nedeni ve 2 düzeltme adımını yaz"
        )
        if _enqueue(runtime, mission_id, objective, department):
            mission = mission_id
            decision["mission"] = mission

    path = _ceo_dir(runtime) / "decisions.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(decision, ensure_ascii=False) + "\n")
    return decision


def decide(runtime_dir: str | Path, question: str) -> dict:
    """Kanıta dayalı karar: brifing + gerekçe, karar kaydına yazılır."""

    runtime = Path(runtime_dir)
    brief = daily_brief(runtime)
    if "zayıf" in question.casefold() or "performans" in question.casefold():
        answer = f"En zayıf halka: {brief.weakest_department or '-'}. Öncelik oraya verilmeli."
        action = "review"
    elif "engel" in question.casefold() or "hata" in question.casefold():
        answer = "Baskın engeller: " + (", ".join(brief.top_causes) or "yok")
        action = "retry-blocked"
    else:
        answer = brief.text()
        action = "brief"
    record = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "type": "decision",
        "question": question[:200],
        "answer": answer,
        "action": action,
        "delivery_rate": round(brief.delivery_rate, 4),
    }
    path = _ceo_dir(runtime) / "decisions.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record
