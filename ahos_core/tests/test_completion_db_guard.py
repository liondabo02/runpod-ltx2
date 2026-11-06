"""Database guard blocks all raw SQL status-only completion bypasses."""

from __future__ import annotations

import json
import sqlite3

import pytest

from ahos.autonomous_company import PersistentMissionQueue, QueueStatus
from ahos.mission_orchestrator import MissionResult, MissionStatus


def _pending(tmp_path):
    db = tmp_path / "mission.db"
    queue = PersistentMissionQueue(db)
    queue.enqueue(
        mission_id="m1", objective="do a small task",
        primary_department="software",
    )
    return db, queue


def test_raw_status_only_sql_completion_is_rejected(tmp_path):
    db, queue = _pending(tmp_path)
    with sqlite3.connect(db) as conn:
        with pytest.raises(sqlite3.IntegrityError, match="consistent result_json"):
            conn.execute(
                "UPDATE missions SET status='completed' WHERE mission_id='m1'"
            )
    assert queue.get("m1").status is QueueStatus.PENDING


def test_blocked_result_json_cannot_be_marked_completed(tmp_path):
    db, queue = _pending(tmp_path)
    with sqlite3.connect(db) as conn:
        with pytest.raises(sqlite3.IntegrityError, match="consistent result_json"):
            conn.execute(
                "UPDATE missions SET status='completed',result_json=? WHERE mission_id='m1'",
                (json.dumps({"status": "blocked"}),),
            )
        with pytest.raises(sqlite3.IntegrityError, match="consistent result_json"):
            conn.execute(
                "UPDATE missions SET status='completed',result_json=? WHERE mission_id='m1'",
                ("invalid-json",),
            )
    assert queue.get("m1").status is QueueStatus.PENDING


def test_valid_completion_via_queue_still_succeeds(tmp_path):
    db, queue = _pending(tmp_path)
    queue.claim_next(owner="worker")
    queue.complete(
        "m1", owner="worker",
        result=MissionResult(
            mission_id="m1", objective="do a small task",
            manager_id="manager", status=MissionStatus.COMPLETED,
            steps=(), reason="test result",
            qa_worker_id="qa-01",
        ),
    )
    assert queue.get("m1").status is QueueStatus.COMPLETED


def test_legacy_invalid_completed_rows_are_unchanged_on_install(tmp_path):
    db, queue = _pending(tmp_path)
    with sqlite3.connect(db) as conn:
        conn.execute("DROP TRIGGER ahos_completed_result_guard_update")
        conn.execute("DROP TRIGGER ahos_completed_result_guard_insert")
        conn.execute("UPDATE missions SET status='completed' WHERE mission_id='m1'")
        conn.commit()
    assert queue.get("m1").status is QueueStatus.COMPLETED

    PersistentMissionQueue(db)  # trigger migration, no historical rewriting
    with sqlite3.connect(db) as conn:
        assert conn.execute(
            "SELECT status,result_json FROM missions WHERE mission_id='m1'"
        ).fetchone() == ("completed", None)
        with pytest.raises(sqlite3.IntegrityError, match="consistent result_json"):
            conn.execute(
                "UPDATE missions SET status='completed',result_json=NULL "
                "WHERE mission_id='m1'"
            )


def test_raw_direct_insert_completed_without_result_is_rejected(tmp_path):
    db, queue = _pending(tmp_path)
    with sqlite3.connect(db) as conn:
        with pytest.raises(sqlite3.IntegrityError, match="consistent result_json"):
            conn.execute(
                "INSERT INTO missions "
                "(mission_id, objective, primary_department, status, created_at, updated_at) "
                "VALUES ('m2', 'other task', 'software', 'completed', 'now', 'now')"
            )
        assert conn.execute(
            "SELECT COUNT(*) FROM missions WHERE mission_id='m2'"
        ).fetchone()[0] == 0
