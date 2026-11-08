"""Eğitim motoru testleri (17 departman / 81 çalışan, 8 soru)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ahos.training import build_course, examine, teach


def _runtime(tmp_path: Path) -> Path:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    con = sqlite3.connect(runtime / "company-service.db")
    con.execute(
        "create table missions (mission_id text, objective text, primary_department text, "
        "status text, updated_at text)"
    )
    con.executemany(
        "insert into missions values (?,?,?,?,datetime('now'))",
        [
            ("CMD-oyun-1", "bölüm ekle", "oyun", "completed"),
            ("CMD-oyun-2", "düzelt", "oyun", "blocked"),
        ],
    )
    con.commit()
    con.close()
    return runtime


def test_build_course_has_eight_questions(tmp_path) -> None:
    runtime = _runtime(tmp_path)

    course = build_course(runtime, "oyun")

    assert len(course.questions) == 8
    assert all(isinstance(question, tuple) and len(question) == 2 for question in course.questions)


def test_build_course_uses_real_queue_numbers(tmp_path) -> None:
    runtime = _runtime(tmp_path)

    course = build_course(runtime, "oyun")

    assert any("tamamlandı" in fact for fact in course.facts)
    assert any("teslim oranı" in fact for fact in course.facts)


def test_examine_returns_score(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    course = build_course(runtime, "oyun")

    result = examine(course, "oyun-manager")

    assert result["worker"] == "oyun-manager"
    assert result["score"] == 100
    assert result["passed"] is True
    assert result["questions"] == 8


def test_teach_writes_report(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    departments = [{"department_id": "oyun", "workers": [{"worker_id": "w1"}, {"worker_id": "w2"}]}]

    report = teach(runtime, departments)

    assert report["departments"] == 1
    assert report["workers"] == 2
    assert report["failed"] == 0
    assert report["average_score"] == 100
    path = Path(runtime).parent / "config" / "training-report.json"
    assert path.exists()
    assert json.loads(path.read_text(encoding="utf-8"))["passed"] == 2
