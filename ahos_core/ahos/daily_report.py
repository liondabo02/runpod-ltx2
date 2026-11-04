"""Günlük rapor — gerçek verilerden markdown üretir (uydurma yok)."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path


def _queue(runtime: Path) -> dict:
    db = runtime / "company-service.db"
    if not db.exists():
        return {}
    try:
        with sqlite3.connect(db) as con:
            return dict(con.execute("select status, count(*) from missions group by status").fetchall())
    except sqlite3.Error:
        return {}


def _load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _count_lines(path: Path) -> int:
    try:
        return len(path.read_text(encoding="utf-8", errors="replace").splitlines()) if path.exists() else 0
    except OSError:
        return 0


def build(runtime_dir) -> str:
    runtime = Path(runtime_dir)
    cfg = runtime.parent / "config"
    today = time.strftime("%Y-%m-%d")
    queue = _queue(runtime)
    training = _load(cfg / "training-report.json")
    health = _load(cfg / "health-report.json")
    minds = _load(cfg / "minds-summary.json")
    pledge = _load(runtime / "minds" / "_pledge.json")

    conversations = _count_lines(runtime / "minds" / "conversations.jsonl")
    thoughts = _count_lines(runtime / "minds" / "thoughts.jsonl")
    plans = _count_lines(runtime / "minds" / "plan-queue.jsonl")
    outcome = _count_lines(runtime / "outcome.jsonl")

    lines = [
        f"# AHOS Günlük Rapor — {today}",
        "",
        f"- Sahip: **{pledge.get('owner', 'bilinmiyor')}**",
        f"- Üretim zamanı: {time.strftime('%Y-%m-%dT%H:%M:%S')}",
        "",
        "## Kuyruk",
        f"- Tamamlanan: **{queue.get('completed', 0)}**",
        f"- Bekleyen: {queue.get('pending', 0)}",
        f"- Engelli: **{queue.get('blocked', 0)}**",
        f"- Başarısız: {queue.get('failed', 0)}",
        f"- İptal: {queue.get('cancelled', 0)}",
        "",
        "## Eğitim",
        f"- Departman: {training.get('departments', 0)} · Çalışan: {training.get('workers', 0)}",
        f"- Geçen: {training.get('passed', 0)} · Kalan: {training.get('failed', 0)} · Ortalama: %{training.get('average_score', 0)}",
        f"- Üretim: {training.get('generated_at', 'yok')}",
        "",
        "## Zihin",
        f"- Zihinli işçi: {minds.get('workers_with_mind', 0)} / {minds.get('total_workers', 0)}",
        f"- Ortalama başarı: %{round(float(minds.get('avg_success_rate', 0)) * 100)}",
        f"- Düşünce kaydı: {thoughts} · Konuşma mesajı: {conversations} · Plan adımı: {plans}",
        "",
        "## Sağlık",
        f"- Durum: **{'SAĞLIKLI' if health.get('ok') else 'SORUN VAR'}**",
    ]
    for check in health.get("checks", []):
        mark = "✅" if check.get("ok") else "❌"
        lines.append(f"  - {mark} {check.get('name')}: {str(check.get('detail'))[:80]}")

    lines += ["", "## Öğrenme", f"- Outcome kaydı: {outcome}", ""]
    return "\n".join(lines)


def write(runtime_dir) -> Path:
    runtime = Path(runtime_dir)
    out_dir = runtime / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    text = build(runtime)
    path = out_dir / f"{time.strftime('%Y-%m-%d')}.md"
    path.write_text(text, encoding="utf-8")
    latest = runtime.parent / "config" / "report-latest.md"
    latest.parent.mkdir(parents=True, exist_ok=True)
    latest.write_text(text, encoding="utf-8")
    return path
