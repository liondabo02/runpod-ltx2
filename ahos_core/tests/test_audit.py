from __future__ import annotations

import json

import pytest

from ahos.audit import AuditIntegrityError, AuditLog


def test_audit_journal_has_stable_ids_and_hash_chain(tmp_path) -> None:
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)

    first = log.append(
        "mission_started",
        {"mission_id": "m-1"},
        correlation_id="mission:m-1",
        timestamp="2026-09-16T12:00:00+00:00",
    )
    second = log.append(
        "mission_completed",
        {"mission_id": "m-1", "status": "completed"},
        correlation_id="mission:m-1",
        timestamp="2026-09-16T12:01:00+00:00",
    )

    assert first.sequence == 1
    assert second.sequence == 2
    assert second.previous_hash == first.event_id
    assert first.event_id != second.event_id
    assert log.verify_integrity() is True


def test_reopened_journal_continues_sequence_and_chain(tmp_path) -> None:
    path = tmp_path / "audit.jsonl"

    first = AuditLog(path).append(
        "routing_decision",
        {"department": "software"},
        correlation_id="mission:m-2",
        timestamp="2026-09-16T12:00:00+00:00",
    )
    second = AuditLog(path).append(
        "execution_attempt",
        {"attempt": 1},
        correlation_id="mission:m-2",
        timestamp="2026-09-16T12:00:10+00:00",
    )

    assert second.sequence == 2
    assert second.previous_hash == first.event_id
    assert AuditLog(path).verify_integrity() is True


def test_integrity_check_detects_tampering(tmp_path) -> None:
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)

    log.append(
        "approval_recorded",
        {"decision": "pending"},
        correlation_id="approval:a-1",
        timestamp="2026-09-16T12:00:00+00:00",
    )

    record = json.loads(path.read_text(encoding="utf-8"))
    record["payload"]["decision"] = "approved"
    path.write_text(json.dumps(record) + "\n", encoding="utf-8")

    with pytest.raises(AuditIntegrityError, match="hash verification"):
        log.verify_integrity()


def test_legacy_records_can_be_extended_without_rewrite(tmp_path) -> None:
    path = tmp_path / "audit.jsonl"
    legacy = {
        "timestamp": "2026-09-16T11:00:00+00:00",
        "event_type": "legacy",
        "payload": {"id": "old-1"},
    }
    original = json.dumps(legacy, sort_keys=True) + "\n"
    path.write_text(original, encoding="utf-8")

    new_event = AuditLog(path).append(
        "mission_started",
        {"id": "m-3"},
        correlation_id="mission:m-3",
        timestamp="2026-09-16T12:00:00+00:00",
    )

    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == original.strip()
    assert new_event.sequence == 2
    assert new_event.previous_hash is not None
    assert AuditLog(path).verify_integrity() is True
