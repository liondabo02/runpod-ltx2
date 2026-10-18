from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from ahos.runtime_audit import RuntimeAuditor


def _write(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


def _healthy_runtime(tmp_path, now):
    _write(tmp_path / "company-service-heartbeat.json", {
        "timestamp": (now - timedelta(seconds=5)).isoformat(),
        "state": "idle",
    })
    _write(tmp_path / "coding-supervisor-queue.json", {
        "a": {"status": "waiting_owner_approval"},
        "b": {"status": "retries_exhausted"},
    })
    _write(tmp_path / "department-service-status.json", {
        "status": "polled",
        "counts": {"waiting_owner_approval": 2},
    })
    _write(tmp_path / "company-service-config.json", {
        "coding_supervisor": {"enabled": True, "secret": "never report me"},
        "holding_brain": {"enabled": True},
    })


def test_runtime_audit_accepts_fresh_enabled_runtime(tmp_path):
    now = datetime(2026, 10, 18, 16, 0, tzinfo=timezone.utc)
    _healthy_runtime(tmp_path, now)
    report = RuntimeAuditor(tmp_path).audit(now=now)
    assert report.healthy is True
    assert report.blockers == ()
    assert report.coding_counts == {
        "retries_exhausted": 1,
        "waiting_owner_approval": 1,
    }


def test_runtime_audit_rejects_stale_heartbeat(tmp_path):
    now = datetime(2026, 10, 18, 16, 0, tzinfo=timezone.utc)
    _healthy_runtime(tmp_path, now - timedelta(minutes=10))
    report = RuntimeAuditor(tmp_path).audit(now=now)
    assert report.healthy is False
    assert "stale_heartbeat" in report.blockers


def test_runtime_audit_fails_closed_when_core_files_are_missing(tmp_path):
    report = RuntimeAuditor(tmp_path).audit(
        now=datetime(2026, 10, 18, 16, 0, tzinfo=timezone.utc)
    )
    assert report.healthy is False
    assert {
        "missing_heartbeat",
        "missing_coding_queue",
        "missing_department_status",
        "missing_service_config",
    }.issubset(report.blockers)
