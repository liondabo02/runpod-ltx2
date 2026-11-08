"""A completed state alone is never evidence of an actual delivered job."""

from __future__ import annotations

import json
import sqlite3

import pytest

from ahos.completion_integrity import (
    classify_completed_payload, main, summarize_completed,
)


def _payload(status="completed", steps=None) -> str:
    if steps is None:
        steps = [{"stage": "completed", "qa_summary": "passed separately"}]
    return json.dumps({
        "status": status,
        "mission_id": "may-contain-private-task-id",
        "steps": steps,
        "reason": "PRIVATE_TASK_CONTENT_DO_NOT_PRINT",
    })


def test_completed_column_with_blocked_payload_is_mismatch():
    assert classify_completed_payload(_payload("blocked")) == "result_not_completed"
    assert classify_completed_payload(None) == "missing_result"
    assert classify_completed_payload("not-json") == "malformed_result"


def test_consistent_narrative_is_not_independent_delivery_proof():
    assert classify_completed_payload(_payload()) == "consistent_but_unverified"
    assert classify_completed_payload(_payload(steps=[])) == "no_steps"
    assert classify_completed_payload(_payload(steps=[
        {"stage": "blocked", "qa_summary": "passed"}
    ])) == "uncompleted_steps"
    assert classify_completed_payload(_payload(steps=[
        {"stage": "completed", "qa_summary": ""}
    ])) == "no_qa_summary"


def test_audit_only_aggregates_and_does_not_modify_db(tmp_path, capsys):
    db = tmp_path / "sample.db"
    with sqlite3.connect(db) as conn:
        conn.execute(
            "CREATE TABLE missions (status TEXT, result_json TEXT, updated_at TEXT)"
        )
        conn.executemany("INSERT INTO missions VALUES (?,?,?)", [
            ("completed", _payload("blocked"), "2026-10-31 20:00"),
            ("completed", _payload(), "2026-10-31 20:01"),
            ("completed", None, "2026-10-31 20:02"),
            ("blocked", _payload("blocked"), "2026-10-31 20:03"),
        ])
    before = db.read_bytes()
    report = summarize_completed(db)
    assert report["total_completed_status"] == 3
    assert report["inconsistent"] == 2
    assert report["payload_categories"]["result_not_completed"] == 1
    assert report["payload_categories"]["consistent_but_unverified"] == 1
    assert report["independent_qa_and_artifact_verified"] == 0
    assert not report["contains_raw_task_data"]

    assert main(["--database", str(db)]) == 2
    output = capsys.readouterr().out
    assert "PRIVATE_TASK_CONTENT_DO_NOT_PRINT" not in output
    assert "may-contain-private-task-id" not in output
    assert db.read_bytes() == before


def test_limited_audit_does_not_claim_all_records_checked(tmp_path):
    db = tmp_path / "sample.db"
    with sqlite3.connect(db) as conn:
        conn.execute(
            "CREATE TABLE missions (status TEXT,result_json TEXT,updated_at TEXT)"
        )
        conn.executemany("INSERT INTO missions VALUES (?,?,?)", [
            ("completed", _payload(), "2026-10-31T20:00:00Z"),
            ("completed", _payload(), "2026-10-31T20:01:00Z"),
        ])
    result = summarize_completed(db, limit=1)
    assert result["audited"] == 1
    assert result["not_audited"] == 1
    assert main(["--database", str(db), "--limit", "1"]) == 2


def test_nonexistent_database_never_created(tmp_path):
    missing = tmp_path / "absent.db"
    with pytest.raises(FileNotFoundError):
        summarize_completed(missing)
    assert main(["--database", str(missing)]) == 2
    assert not missing.exists()


def test_direct_sql_completion_bypass_detected_without_running_code(tmp_path):
    from ahos.completion_integrity import find_unsafe_direct_completion_updates

    package = tmp_path / "ahos"
    package.mkdir()
    (package / "unsafe.py").write_text(
        'def bypass(conn):\n'
        '    conn.execute("update missions set status=\'completed\' where mission_id=?", ("a",))\n',
        encoding="utf-8",
    )
    (package / "safe.py").write_text(
        'def complete(queue, ident, owner, result):\n'
        '    queue.complete(ident, owner=owner, result=result)\n',
        encoding="utf-8",
    )
    findings = find_unsafe_direct_completion_updates(package)
    assert len(findings) == 1
    assert findings[0].startswith("unsafe.py:")
