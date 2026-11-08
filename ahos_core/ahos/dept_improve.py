"""Departman kendini geliştirme — iş olmasa bile her turda ilerleme üretir.

Her departman için:
- geçmiş (tamamlanan / engellenen / bekleyen) ve zihin ortalaması okunur
- 1-3 somut iyileştirme maddesi üretilir (kural tabanlı, gerçek veriden)
- runtime/departments/<dep>-improvements.jsonl dosyasına yazılır
- config/departments-roadmap.json içinde departman başına son hedefler tutulur

Model gerekmez; tüm çıktı gerçek sayılardan türetilir.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path


def _counts(runtime: Path) -> dict[str, dict[str, int]]:
    db = runtime / "company-service.db"
    if not db.exists():
        return {}
    out: dict[str, dict[str, int]] = {}
    try:
        with sqlite3.connect(db) as con:
            for dep, status, count in con.execute(
                "select primary_department, status, count(*) from missions group by 1,2"
            ):
                out.setdefault(str(dep or "genel"), {})[str(status)] = int(count)
    except sqlite3.Error:
        return out
    return out


def _mind_rate(runtime: Path, dep: str) -> tuple[float, int]:
    path = runtime / "minds" / "departments" / f"{dep}.json"
    if not path.exists():
        return 0.0, 0
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return 0.0, 0
    lessons = data.get("lessons") or []
    return (1.0 if lessons else 0.0), len(lessons)


def plan_for(dep: str, stats: dict[str, int], mind_lessons: int) -> list[str]:
    completed = stats.get("completed", 0)
    blocked = stats.get("blocked", 0)
    pending = stats.get("pending", 0)
    failed = stats.get("failed", 0)
    total = max(1, completed + blocked + pending + failed)
    rate = completed / total

    items: list[str] = []
    if blocked:
        items.append(f"engel {blocked} → kök neden analizi ve tekrar deneme politikası")
    if failed:
        items.append(f"başarısız {failed} → hata sınıflandırması ve önleyici kontrol")
    if rate < 0.6:
        items.append(f"teslim oranı %{round(rate * 100)} → kapsamı küçült (tek dosya/tek adım)")
    if pending > 20:
        items.append(f"bekleyen {pending} → günlük teslim hedefi ve öncelik sırası")
    if mind_lessons < 3:
        items.append("zihin dersleri az → departman içi konuşma turu artırılmalı")
    if not items:
        items.append("istikrar iyi → yeni yetenek alanı dene (otomasyon/ölçüm)")
    return items[:3]


def run(runtime_dir) -> dict:
    runtime = Path(runtime_dir)
    cfg = runtime.parent / "config"
    cfg.mkdir(parents=True, exist_ok=True)
    book = json.loads((cfg / "departments.json").read_text(encoding="utf-8"))
    deps = book.get("departments") if isinstance(book, dict) else book

    counts = _counts(runtime)
    out_dir = runtime / "departments"
    out_dir.mkdir(parents=True, exist_ok=True)

    roadmap: dict[str, dict] = {}
    total_items = 0
    for dep in deps or []:
        dep_id = str(dep.get("department_id") or "")
        if not dep_id:
            continue
        stats = counts.get(dep_id, {})
        rate, lessons = _mind_rate(runtime, dep_id)
        items = plan_for(dep_id, stats, lessons)
        total_items += len(items)
        record = {
            "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "department": dep_id,
            "workers": len(dep.get("workers") or []),
            "stats": stats,
            "items": items,
        }
        with open(out_dir / f"{dep_id}-improvements.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        roadmap[dep_id] = {"last_at": record["at"], "items": items, "stats": stats}

    (cfg / "departments-roadmap.json").write_text(
        json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "departments": roadmap},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {"departments": len(roadmap), "items": total_items}
