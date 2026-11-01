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
import sqlite3
import time
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
    """worker → (koşu sayısı, son koşu zamanı)."""

    ledger = runtime / "worker-metrics.jsonl"
    stats: dict[str, tuple[int, float]] = {}
    if not ledger.exists():
        return stats
    now = time.time()
    for line in ledger.read_text(encoding="utf-8", errors="replace").splitlines()[-2000:]:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        worker = str(row.get("worker_id") or "")
        if not worker:
            continue
        runs, last = stats.get(worker, (0, 0.0))
        stats[worker] = (runs + 1, max(last, now - 60))
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

    studied: list[str] = []
    for dep in departments:
        if len(studied) >= limit:
            break
        dep_id = str(dep.get("department_id") or "")
        for worker in dep.get("workers") or []:
            if len(studied) >= limit:
                break
            worker_id = str(worker.get("worker_id") or "")
            if not worker_id:
                continue
            # CEO dahil herkes: koşusu az olan öğrenmeye gider.
            worker_runs = runs.get(worker_id, (0, 0.0))[0]
            if worker_runs > 5:
                continue
            lesson = _lesson(dep_id, worker_id, counts, worker_runs)
            path = directory / f"{dep_id}.jsonl"
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(lesson, ensure_ascii=False) + "\n")
            studied.append(worker_id)

    summary = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "studied": studied,
        "count": len(studied),
        "departments": len(departments),
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
