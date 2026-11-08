"""Blocked mission triage never mutates status or prints sensitive error text."""

from __future__ import annotations

import json
import sqlite3

from ahos.blocked_triage import classify_error, summarize, main


def test_errors_categorized_without_exposing_details():
    assert classify_error("model_unavailable: MODEL_X secret content") == "model_unavailable"
    assert classify_error("QA failed after acceptance: private notes") == "qa_rejected"
    assert classify_error("HTTP 429: sensitive request") == "rate_limit"
    assert classify_error("") == "no_reason_recorded"


def test_blocked_queue_summary_is_read_only_and_redacted(tmp_path, capsys):
    db = tmp_path / "missions.db"
    with sqlite3.connect(db) as con:
        con.execute("CREATE TABLE missions(status TEXT, last_error TEXT, updated_at TEXT)")
        con.executemany(
            "INSERT INTO missions VALUES(?,?,?)",
            [
                ("blocked", "model_unavailable: secret-token-do-not-print", "2026-10-31 20:01"),
                ("blocked", "QA failed: confidential-artifact", "2026-10-31 20:02"),
                ("cancelled", "do-not-expose-details", "2026-10-31 20:03"),
                ("completed", "", "2026-10-31 20:04"),
            ],
        )
    before = db.read_bytes()
    result = summarize(db)
    assert result["status_counts"] == {"blocked": 2, "cancelled": 1, "completed": 1}
    assert result["blocked_reason_categories"] == {
        "qa_rejected": 1, "model_unavailable": 1,
    }
    assert result["contains_raw_error_text"] is False
    assert db.read_bytes() == before

    assert main(["--database", str(db)]) == 0
    output = capsys.readouterr().out
    data = json.loads(output)
    assert data["ok"] is True
    assert "secret-token-do-not-print" not in output
    assert "confidential-artifact" not in output
    assert db.read_bytes() == before


def test_missing_database_blocks_without_creating_file(tmp_path):
    missing = tmp_path / "absent.db"
    assert main(["--database", str(missing)]) == 2
    assert not missing.exists()


def test_qa_subreason_categories_are_redacted():
    from ahos.blocked_triage import qa_detail
    assert qa_detail("QA failed: missing artifact /private/path") == "missing_artifact"
    assert qa_detail("QA failed: browser unavailable at secret URL") == "browser_failure"
    assert qa_detail("QA failed: unknown private payload") == "other_qa"


def test_structured_qa_step_reason_diagnosed_without_leaking(tmp_path):
    db = tmp_path / "missions.db"
    with sqlite3.connect(db) as con:
        con.execute(
            "CREATE TABLE missions(status TEXT,last_error TEXT,updated_at TEXT,result_json TEXT)"
        )
        result = json.dumps({
            "steps": [{
                "stage": "blocked",
                "qa_summary": "QA rejected: missing artifact /PRIVATE/secret",
                "worker_summary": "do not expose user text",
            }]
        })
        con.execute(
            "INSERT INTO missions VALUES(?,?,?,?)",
            ("blocked", "QA failed: confidential error", "2026-10-31 21:00", result),
        )
    report = summarize(db)
    assert report["last_step_stages"] == {"blocked": 1}
    assert report["step_qa_detail_categories"] == {"missing_artifact": 1}
    assert "secret" not in json.dumps(report)
