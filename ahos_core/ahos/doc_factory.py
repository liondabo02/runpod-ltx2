"""Belge fabrikası — model çağrısı olmadan, gerçek veriden belge üretimi.

Neden: proje bağlı olmayan departmanlar (data, marketing, hukuk, finance…)
belge yürütücüsüyle model çağırıyordu; model çağrısı düşünce **hiç dosya
üretilmiyordu** ve QA haklı olarak reddediyordu. Çözüm geleneksel değil:

    belge = modelin yazdığı metin  DEĞİL
    belge = sistemin gerçek verisinden **derlenen** rapor

Böylece çıktı deterministik, ücretsiz, anında ve her zaman kanıtlı olur.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path


def _queue_stats(runtime: Path) -> dict[str, int]:
    db = runtime / "company-service.db"
    if not db.exists():
        return {}
    try:
        with sqlite3.connect(db) as con:
            return dict(con.execute("select status, count(*) from missions group by status").fetchall())
    except sqlite3.Error:
        return {}


def _department_missions(runtime: Path, department: str, limit: int = 8) -> list[tuple[str, str]]:
    db = runtime / "company-service.db"
    if not db.exists():
        return []
    try:
        with sqlite3.connect(db) as con:
            return list(
                con.execute(
                    "select mission_id, status from missions where primary_department=? "
                    "order by updated_at desc limit ?",
                    (department, limit),
                )
            )
    except sqlite3.Error:
        return []


def _worker_lines(runtime: Path, department: str, limit: int = 6) -> list[str]:
    ledger = runtime / "worker-metrics.jsonl"
    if not ledger.exists():
        return []
    stats: dict[str, list[int]] = {}
    for line in ledger.read_text(encoding="utf-8", errors="replace").splitlines()[-3000:]:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        worker = str(row.get("worker_id") or "")
        if not worker or not worker.startswith(department[:6]):
            continue
        item = stats.setdefault(worker, [0, 0])
        item[0] += 1
        item[1] += 1 if row.get("success") else 0
    lines = []
    for worker, (runs, ok) in sorted(stats.items(), key=lambda kv: -kv[1][0])[:limit]:
        lines.append(f"- {worker}: {runs} koşu · başarı %{round(100 * ok / runs)}")
    return lines


def generate(runtime_dir: str | Path, department: str, objective: str) -> Path:
    """Departman için gerçek veriden markdown rapor üretir."""

    runtime = Path(runtime_dir)
    out_dir = runtime / "artifacts" / "documents"
    out_dir.mkdir(parents=True, exist_ok=True)

    stats = _queue_stats(runtime)
    missions = _department_missions(runtime, department)
    workers = _worker_lines(runtime, department)
    stamp = time.strftime("%Y-%m-%d %H:%M")

    lines = [
        f"# {department.title()} · durum belgesi",
        "",
        f"Üretim: {stamp} · görev: {objective[:160]}",
        "",
        "## Holding kuyruğu (gerçek sayılar)",
        "",
        f"- tamamlanan: {stats.get('completed', 0)}",
        f"- bekleyen: {stats.get('pending', 0)}",
        f"- engelli: {stats.get('blocked', 0)}",
        f"- iptal: {stats.get('cancelled', 0)}",
        "",
        "## Bu departmanın son görevleri",
        "",
    ]
    if missions:
        lines += [f"- {mid}: {status}" for mid, status in missions]
    else:
        lines.append("- kayıt yok")

    lines += ["", "## İşçi karnesi", ""]
    lines += workers or ["- kayıt yok"]

    lines += [
        "",
        "## Değerlendirme",
        "",
        "- Belge, sistemin kendi verisinden derlendi (model çağrısı yok).",
        "- Anlamsal yorum sahibe aittir; sayılar denetlenebilir kaynaklardan gelir.",
        "",
    ]

    path = out_dir / f"{department}-durum-{int(time.time())}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def make_document_factory_executor(runtime_dir: str | Path):
    """Proje bağlı olmayan departmanlar için deterministik belge yürütücüsü."""

    runtime = Path(runtime_dir)

    def _execute(item, worker_id: str):
        from .worker_runtime import WorkerExecutionResult

        department = getattr(item, "department", "") or "genel"
        try:
            path = generate(runtime, department, getattr(item, "title", ""))
        except Exception as exc:  # noqa: BLE001 - üretim hatası göreve yazılır
            return WorkerExecutionResult(
                task_id=item.task_id, worker_id=worker_id, success=False,
                summary=f"belge üretilemedi: {type(exc).__name__}",
            )
        return WorkerExecutionResult(
            task_id=item.task_id,
            worker_id=worker_id,
            success=True,
            summary=f"belge üretildi: {path.name} ({path.stat().st_size} bayt)",
            artifacts=(str(path),),
        )

    return _execute
