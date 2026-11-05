"""Kalp atışı — bilgisayar kapalıyken bile çalışan başsız döngü.

GitHub Actions zamanlayıcısı bu modülü çağırır:
    python -m ahos.heartbeat

Yaptığı iş (tek tur):
1. runtime dizinini ve departman verisini hazırlar
2. sahiplik kaydını doğrular
3. işçi zihni turu (düşün, hedef, plan, öngörü)
4. işçiler arası konuşma
5. plan → görev dönüşümü
6. eğitim + günlük rapor
7. sonucu `config/heartbeat.json` ve `config/report-latest.md` olarak yazar

Durum dosyaları (db, minds) repoya girmez; yalnız özet raporlar commit edilir.
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Mood:
    """Duygu durumu — gerçek verilerden türetilir (uydurma yok)."""

    energy: float = 0.5
    stress: float = 0.0
    focus: float = 0.5
    label: str = "nötr"
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "energy": round(self.energy, 3),
            "stress": round(self.stress, 3),
            "focus": round(self.focus, 3),
            "label": self.label,
            "notes": self.notes[:4],
        }


def mood_from(queue: dict, mind_rate: float = 0.0) -> Mood:
    completed = int(queue.get("completed", 0))
    blocked = int(queue.get("blocked", 0))
    pending = int(queue.get("pending", 0))
    total = max(1, completed + blocked + pending)

    stress = round(min(1.0, blocked / total * 2.0), 3)
    energy = round(max(0.1, min(1.0, 0.4 + mind_rate * 0.6)), 3)
    focus = round(max(0.1, min(1.0, 1.0 - stress * 0.7)), 3)

    if stress >= 0.6:
        label = "baskı altında"
    elif energy >= 0.8 and stress < 0.3:
        label = "motive"
    elif pending > 100:
        label = "yük altında"
    else:
        label = "dengeli"

    notes = [f"engel oranı {round(blocked / total * 100)}%", f"bekleyen {pending}"]
    return Mood(energy=energy, stress=stress, focus=focus, label=label, notes=notes)


def _queue(db: Path) -> dict:
    import sqlite3

    if not db.exists():
        return {}
    try:
        with sqlite3.connect(db) as con:
            return dict(con.execute("select status, count(*) from missions group by status").fetchall())
    except sqlite3.Error:
        return {}


def run(core: Path | None = None) -> dict:
    core = core or Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(core))
    runtime = core / "runtime"
    runtime.mkdir(exist_ok=True)
    cfg = core / "config"
    cfg.mkdir(exist_ok=True)

    book_path = runtime / "departments.json"
    if not book_path.exists():
        seed = cfg / "departments.json"
        if seed.exists():
            book_path.write_text(seed.read_text(encoding="utf-8"), encoding="utf-8")

    departments: list[dict] = []
    if book_path.exists():
        book = json.loads(book_path.read_text(encoding="utf-8"))
        departments = book.get("departments") if isinstance(book, dict) else book

    os.environ.setdefault("AHOS_OWNER", "harun")

    from .commune import converse
    from .daily_report import write as write_report
    from .mind_feedback import flush_plan_queue
    from .sovereign import ensure
    from .training import teach
    from .worker_mind import summarize, tick

    pledge = ensure(runtime)
    minds = tick(runtime, departments or [], limit=20)
    talk = converse(runtime, departments or [], rounds=2)
    plans = flush_plan_queue(runtime, limit=10)

    training = {"departments": 0, "workers": 0, "passed": 0}
    try:
        training = teach(runtime, departments or [])
    except Exception:  # noqa: BLE001
        pass

    # Departman kendini gelistirme turu (is olsa da olmasa da)
    try:
        from .dept_improve import run as _dept_run

        dept = _dept_run(runtime)
    except Exception:  # noqa: BLE001
        dept = {}

    # Oylama: departmanlar turun onceligini birlikte belirler (kolektif karar)
    try:
        from .consensus import vote as _vote

        consensus = _vote(runtime, "genel", "bu turun onceligi",
                          ["engel tasfiyesi", "kuyruk bosaltma", "gelisim"])
    except Exception:  # noqa: BLE001
        consensus = {}

    summary = summarize(runtime)
    queue = _queue(runtime / "company-service.db")
    mood = mood_from(queue, float(summary.get("avg_success_rate", 0)))

    report_path = write_report(runtime)
    result = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "owner": pledge.get("owner"),
        "departments": len(departments or []),
        "minds": minds,
        "commune": talk,
        "plan_queue": plans,
        "training": {k: training.get(k) for k in ("departments", "workers", "passed", "average_score")},
        "queue": queue,
        "mood": mood.to_dict(),
        "consensus": consensus,
        "departments_improved": dept,
        "report": str(report_path.relative_to(core)),
    }
    (cfg / "heartbeat.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> int:
    result = run()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
