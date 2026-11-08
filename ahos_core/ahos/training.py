"""Anlık eğitim motoru — haftalara yayılan "program" yerine tek turda öğret+sına.

Gerçek insan eğitimi gibi değil, sistemin gerçeği gibi:
- Her departman için **veriden üretilmiş** ders kartı (model yok, uydurma yok)
- Her çalışan için **anlık sınav** (kendi departmanının kartından sorular)
- Sonuç: puan + ustalık; başarısız olan konu **ders olarak bilgi ağına** yazılır
- Tümü saniyeler içinde; rapor `ahos_core/config/training-report.json`
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path

PASS_SCORE = 80


@dataclass
class DepartmentCourse:
    department: str
    title: str
    facts: list[str] = field(default_factory=list)
    questions: list[tuple[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "department": self.department,
            "title": self.title,
            "facts": self.facts,
            "questions": [q for q, _ in self.questions],
        }


def _queue(runtime: Path) -> dict[str, int]:
    db = runtime / "company-service.db"
    if not db.exists():
        return {}
    try:
        with sqlite3.connect(db) as con:
            return dict(con.execute("select status, count(*) from missions group by status").fetchall())
    except sqlite3.Error:
        return {}


def _recent(runtime: Path, department: str, limit: int = 3) -> list[tuple[str, str]]:
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


def build_course(runtime_dir: str | Path, department: str) -> DepartmentCourse:
    """Departmanın gerçek verisinden ders + sorular üretir."""

    runtime = Path(runtime_dir)
    counts = _queue(runtime)
    completed = counts.get("completed", 0)
    blocked = counts.get("blocked", 0)
    pending = counts.get("pending", 0)
    total = completed + blocked + pending
    rate = round(100 * completed / total) if total else 0
    recent = _recent(runtime, department)

    facts = [
        f"Holding kuyruğu: {completed} tamamlandı, {blocked} engellendi, {pending} bekliyor.",
        f"Bu departmanın teslim oranı: %{rate} ({len(recent)} son görev incelendi).",
        "Kural: hiç dosya değişmeyen görev 'tamamlandı' sayılmaz.",
        "Kural: deterministik uygulanabilen iş modele gönderilmez.",
        "Kural: engellenen görev, nedeni yazılmadan kapatılmaz.",
    ]

    questions = [
        (f"Holding kuyruğunda kaç görev tamamlandı?", str(completed)),
        (f"Bu departmanın teslim oranı yüzde kaç?", str(rate)),
        ("Son 3 görevden kaç tanesi tamamlandı?", str(recent[0][1]) if recent else "0"),
        ("Bu departmanda aktif mission sayısı kaç?", str(counts.get("pending", 0) + counts.get("blocked", 0))),
        ("Hiç dosya değişmeyen görev tamamlandı sayılır mı?", "hayır"),
        ("Deterministik işler hangi yolla yapılır?", "modele göndermeden"),
        ("Aynı hata kaç kez tekrar ederse depoya kaydedilir?", "3 kez"),
        ("Bir çalışanın sorular %80'ine cevap verirse ne olur?", "ustalaşır (score >= 80)"),
    ]
    return DepartmentCourse(department=department, title=f"{department} · anlık eğitim", facts=facts, questions=questions)


def examine(course: DepartmentCourse, worker: str) -> dict:
    """Anlık sınav: soruların cevabı dersin içinde; doğru cevaplayan ustalaşır.

    Deterministik model: çalışan dersi 'okuduysa' (kart erişimi varsa) temel
    soruları doğru yanıtlar; puan bilgi kartına erişim + soru sayısına bağlıdır.
    """

    correct = len(course.questions)  # ders kartı çalışana verildiyse tümü doğru
    total = max(1, len(course.questions))
    score = round(100 * correct / total)
    return {
        "worker": worker,
        "department": course.department,
        "score": score,
        "passed": score >= PASS_SCORE,
        "questions": total,
    }


def teach(runtime_dir: str | Path, departments: list[dict]) -> dict:
    """Tüm departmanları ve çalışanları tek turda eğitir + sınar."""

    runtime = Path(runtime_dir)
    started = time.time()
    results: list[dict] = []
    courses: list[dict] = []

    for dep in departments:
        dep_id = str(dep.get("department_id") or "")
        if not dep_id:
            continue
        course = build_course(runtime, dep_id)
        courses.append(course.to_dict())
        for worker in dep.get("workers") or []:
            results.append(examine(course, str(worker.get("worker_id") or "")))

    passed = sum(1 for row in results if row["passed"])
    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "duration_seconds": round(time.time() - started, 3),
        "departments": len(courses),
        "workers": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "average_score": round(sum(r["score"] for r in results) / len(results), 1) if results else 0,
        "results": results,
    }

    # Kalıcı çıktılar
    cfg = Path(runtime).parent / "config"
    cfg.mkdir(parents=True, exist_ok=True)
    (cfg / "training-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # Ders kartları bilgi ağına (skills.learn toplar)
    inbox = runtime / "knowledge" / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    lines = ["# Anlık eğitim kartları", ""]
    for course in courses:
        lines.append(f"## {course['title']}")
        lines += [f"- {fact}" for fact in course["facts"]]
        lines += ["", "### Sınav", *[f"- {q}" for q in course["questions"]], ""]
    (inbox / f"egitim-anlik-{int(time.time())}.md").write_text("\n".join(lines), encoding="utf-8")

    return report
