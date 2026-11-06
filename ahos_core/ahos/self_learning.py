"""Sürekli öğrenme — boşta kalan her çalışan (CEO dahil) kendi kendine öğrenir.

Fikir: ortak alanda boş beklemek yerine, her çalışan kendi departmanının gerçek
verisinden **mikro ders** üretir, kendine **test sorusu** sorar ve sonucu kaydeder.
Model çağrısı yok; tamamen deterministik ve ucuz.

Döngü her turda:
1. Boşta olan işçileri bul (son N dakikada koşusu olmayanlar).
2. Her biri için: veriden ders kartı + 1 test sorusu + cevap üret.
3. İlerlemeyi `runtime/learning/<departman>.jsonl` dosyasına yaz.
4. Öğrenme sayacı ve ustalık yüzdesi hesaplanır.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

IDLE_MINUTES = 30
STUDY_PER_TICK = 6


def _book(runtime: Path) -> list[dict]:
    try:
        payload = json.loads((runtime / "departments.json").read_text(encoding="utf-8"))
        return payload.get("departments") if isinstance(payload, dict) else payload
    except (OSError, json.JSONDecodeError):
        return []


def _worker_runs(runtime: Path) -> dict[str, tuple[int, float]]:
    """Return observed run counts and actual latest UTC timestamps per worker."""
    ledger = runtime / "worker-metrics.jsonl"
    stats: dict[str, tuple[int, float]] = {}
    if not ledger.exists():
        return stats

    for line in ledger.read_text(encoding="utf-8", errors="replace").splitlines()[-2000:]:
        try:
            row = json.loads(line)
        except (ValueError, TypeError):
            continue
        if not isinstance(row, dict):
            continue
        worker = str(row.get("worker_id") or "")
        if not worker:
            continue
        raw_at = row.get("at") or ""
        try:
            stamp = datetime.fromisoformat(str(raw_at).replace("Z", "+00:00"))
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=timezone.utc)
            actual_last = stamp.timestamp()
        except (ValueError, TypeError, OverflowError):
            actual_last = 0.0
        count, previous = stats.get(worker, (0, 0.0))
        stats[worker] = count + 1, max(previous, actual_last)
    return stats


def _queue_counts(runtime: Path) -> dict[str, int]:
    db = runtime / "company-service.db"
    if not db.exists():
        return {}
    try:
        with sqlite3.connect(db) as con:
            return dict(con.execute("select status, count(*) from missions group by status").fetchall())
    except sqlite3.Error:
        return {}


def _lesson(department: str, worker: str, counts: dict[str, int], runs: int) -> dict:
    """Gerçek veriden mikro ders + test sorusu üretir."""

    completed = counts.get("completed", 0)
    blocked = counts.get("blocked", 0)
    pending = counts.get("pending", 0)
    total = completed + blocked + pending
    rate = round(100 * completed / total) if total else 0

    question, answer = {
        "quality": ("Kabul kapısı geçmeyen iş ne olur?", "Engellenir; kanıt yoksa teslim sayılmaz."),
        "guvenlik": ("Kopya dizinlere yazmak neden yasak?", "Kaynak bozulur; kabul kapısı geri alır."),
        "software": ("Küçük görevde hangi yol önce denenir?", "Deterministik yama; model sonra."),
        "oyun": ("Oyun testinde ne ölçülür?", "Tamamlanma, yıldız, hata oranı, süre."),
        "data": ("Rapor hangi kaynaktan üretilir?", "Kuyruk ve işçi karnesi; model değil."),
    }.get(department, ("Boşta kalan çalışan ne yapar?", "Mikro ders üretir ve kendini test eder."))

    return {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "worker": worker,
        "department": department,
        "lesson": (
            f"Kuyruk: {completed} tamam / {blocked} engel / {pending} bekleyen "
            f"(teslim %{rate}). Bu işçinin {runs} koşusu var."
        ),
        "question": question,
        "answer": answer,
        "learned": True,
    }


def tick(runtime_dir: str | Path, *, limit: int = STUDY_PER_TICK) -> dict:
    """Boştaki çalışanlara öğrenme görevi verir; ilerlemeyi kaydeder."""

    runtime = Path(runtime_dir)
    departments = _book(runtime)
    runs = _worker_runs(runtime)
    counts = _queue_counts(runtime)

    directory = runtime / "learning"
    directory.mkdir(parents=True, exist_ok=True)

    # Persistent round-robin: workers farther down the roster must not starve.
    roster: list[tuple[str, str]] = []
    seen: set[str] = set()
    for dep in departments:
        dep_id = str(dep.get("department_id") or "")
        for worker in dep.get("workers") or []:
            worker_id = str(worker.get("worker_id") or "")
            if worker_id and worker_id not in seen:
                seen.add(worker_id)
                roster.append((dep_id, worker_id))

    cursor_path = directory / ".cursor.json"
    try:
        cursor = int(json.loads(cursor_path.read_text(encoding="utf-8")).get("next", 0))
    except (OSError, ValueError, TypeError, AttributeError):
        cursor = 0
    start = cursor % len(roster) if roster else 0
    now = time.time()
    studied: list[str] = []
    busy = 0
    checked = 0
    max_count = max(0, int(limit))
    for offset in range(len(roster)):
        if len(studied) >= max_count:
            break
        dep_id, worker_id = roster[(start + offset) % len(roster)]
        checked += 1
        worker_runs, last_observed = runs.get(worker_id, (0, 0.0))
        if last_observed and now - last_observed < IDLE_MINUTES * 60:
            busy += 1
            continue
        lesson = _lesson(dep_id, worker_id, counts, worker_runs)
        # A generated micro-lesson is not proof of increased model capability.
        lesson["learning_mode"] = "deterministic_micro_lesson"
        lesson["verified_skill_gain"] = False
        path = directory / f"{dep_id}.jsonl"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(lesson, ensure_ascii=False) + "\n")
        studied.append(worker_id)

    next_cursor = (start + checked) % len(roster) if roster else 0
    temporary = cursor_path.with_name(cursor_path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temporary.write_text(
            json.dumps({"next": next_cursor, "rostered": len(roster),
                        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S")}),
            encoding="utf-8",
        )
        os.replace(temporary, cursor_path)
    finally:
        temporary.unlink(missing_ok=True)

    summary = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "studied": studied,
        "count": len(studied),
        "departments": len(departments),
        "rostered": len(roster),
        "skipped_recently_active": busy,
        "next_cursor": next_cursor,
    }
    (directory / "last-run.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary


def progress(runtime_dir: str | Path) -> dict:
    """Departman bazında öğrenme ilerlemesi."""

    runtime = Path(runtime_dir)
    directory = runtime / "learning"
    result: dict[str, int] = {}
    if not directory.exists():
        return result
    for path in directory.glob("*.jsonl"):
        result[path.stem] = len(path.read_text(encoding="utf-8", errors="replace").splitlines())
    return result
