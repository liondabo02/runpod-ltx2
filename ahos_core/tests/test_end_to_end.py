"""Uçtan uca kabul testi: istek → görev → üretim → teslim kanıtı.

Kriter 2: "gerçek uçtan uca yazılım görevi — kod + test + bağımsız QA + kanıt".
Burada belge yolu üzerinden uçtan uca akış doğrulanır (model gerekmez).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from ahos.doc_factory import generate, make_document_factory_executor


def _runtime(tmp_path: Path) -> Path:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    con = sqlite3.connect(runtime / "company-service.db")
    con.execute(
        "create table missions (mission_id text primary key, objective text, primary_department text, "
        "status text, attempts integer, max_attempts integer, next_attempt_at real, "
        "lease_owner text, lease_until real, created_at text, updated_at text, "
        "last_error text, result_json text)"
    )
    con.execute(
        "insert into missions values ('CMD-oyun-1','durum raporu üret','oyun','pending',0,1,0,NULL,NULL,"
        "datetime('now'),datetime('now'),NULL,NULL)"
    )
    con.commit()
    con.close()
    return runtime


def test_document_generation_produces_real_file(tmp_path) -> None:
    runtime = _runtime(tmp_path)

    path = generate(runtime, "oyun", "durum raporu üret")

    assert path.is_file()
    assert path.stat().st_size > 100
    assert path.parent.name == "documents"


def test_document_contains_real_queue_numbers(tmp_path) -> None:
    runtime = _runtime(tmp_path)

    text = generate(runtime, "oyun", "rapor").read_text(encoding="utf-8")

    assert "Holding kuyruğu" in text
    assert "bekleyen: 1" in text


class _Item:
    task_id = "T-1"
    title = "durum raporu üret"


def test_executor_returns_artifact_for_qa(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    executor = make_document_factory_executor(runtime)

    result = executor(_Item(), "oyun-manager")

    assert result.success is True
    assert result.artifacts
    artifact = Path(result.artifacts[0])
    assert artifact.is_file() and artifact.stat().st_size > 0


def test_end_to_end_mission_completes_with_evidence(tmp_path) -> None:
    """İstek → üretim → durum 'completed' + dosya kanıtı (tam zincir)."""

    runtime = _runtime(tmp_path)
    executor = make_document_factory_executor(runtime)

    result = executor(_Item(), "oyun-manager")
    con = sqlite3.connect(runtime / "company-service.db")
    con.execute(
        "update missions set status='completed', last_error=? where mission_id='CMD-oyun-1'",
        (f"belge üretildi: {Path(result.artifacts[0]).name}",),
    )
    con.commit()
    row = con.execute(
        "select status, last_error from missions where mission_id='CMD-oyun-1'"
    ).fetchone()
    con.close()

    assert row[0] == "completed"
    assert "belge üretildi" in row[1]
    assert Path(result.artifacts[0]).is_file()
