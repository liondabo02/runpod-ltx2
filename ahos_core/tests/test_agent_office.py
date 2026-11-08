from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ahos import agent_office


def _runtime(tmp_path: Path) -> Path:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    book = {
        "departments": [
            {
                "department_id": "oyun",
                "name": "Oyun",
                "mission": "oyun üret",
                "workers": [
                    {"worker_id": "oyun-manager", "name": "Oyun Yöneticisi", "role": "department_manager"},
                    {"worker_id": "oyun-eng", "name": "Mühendis", "role": "engineer"},
                ],
            }
        ]
    }
    (runtime / "departments.json").write_text(json.dumps(book), encoding="utf-8")
    (runtime / "worker-metrics.jsonl").write_text(
        "\n".join(
            json.dumps({"worker_id": "oyun-manager", "success": True, "at": "2026-10-31T10:00:00", "seconds": 2})
            for _ in range(4)
        )
        + "\n"
        + "\n".join(
            json.dumps({"worker_id": "oyun-eng", "success": False, "at": "2026-10-31T10:05:00", "seconds": 30})
            for _ in range(2)
        )
        + "\n",
        encoding="utf-8",
    )
    con = sqlite3.connect(runtime / "company-service.db")
    con.execute(
        "create table missions (mission_id text, objective text, primary_department text, "
        "status text, updated_at text, last_error text)"
    )
    con.executemany(
        "insert into missions values (?,?,?,?,datetime('now'),?)",
        [
            ("CMD-oyun-1", "yeni bölüm ekle", "oyun", "running", None),
            ("CMD-oyun-2", "rapor yaz", "oyun", "completed", None),
            ("CMD-oyun-3", "onay gerekiyor", "oyun", "blocked", "sahip onayı bekleniyor"),
        ],
    )
    con.commit()
    con.close()
    return runtime


def test_snapshot_lists_departments_and_workers(tmp_path) -> None:
    runtime = _runtime(tmp_path)

    payload = agent_office.snapshot(runtime)

    assert payload["totals"]["departments"] == 1
    assert payload["totals"]["workers"] == 2
    assert payload["departments"][0]["department_id"] == "oyun"


def test_snapshot_marks_running_department(tmp_path) -> None:
    runtime = _runtime(tmp_path)

    payload = agent_office.snapshot(runtime)

    assert payload["departments"][0]["state"] == "çalışıyor"
    assert payload["departments"][0]["active"]["mission_id"] == "CMD-oyun-1"


def test_worker_rate_is_computed(tmp_path) -> None:
    runtime = _runtime(tmp_path)

    payload = agent_office.snapshot(runtime)
    workers = {w["worker_id"]: w for w in payload["departments"][0]["workers"]}

    assert workers["oyun-manager"]["rate"] == 1.0
    assert workers["oyun-eng"]["rate"] == 0.0


def test_feed_returns_recent_events(tmp_path) -> None:
    runtime = _runtime(tmp_path)

    events = agent_office.feed(runtime, limit=5)

    assert events
    assert "mission" in events[0]


def test_approvals_lists_blocked_with_approval_reason(tmp_path) -> None:
    runtime = _runtime(tmp_path)

    items = agent_office.approvals(runtime)

    assert len(items) == 1
    assert items[0]["mission_id"] == "CMD-oyun-3"


def test_worklog_roundtrip(tmp_path) -> None:
    runtime = _runtime(tmp_path)

    agent_office.write_worklog(runtime, "oyun", "3. bölüm yarım kaldı; menü eklenecek.")

    text = agent_office.read_worklog(runtime, "oyun")
    assert "3. bölüm yarım kaldı" in text


def test_snapshot_is_json_serialisable(tmp_path) -> None:
    runtime = _runtime(tmp_path)

    payload = agent_office.snapshot(runtime)

    assert json.dumps(payload, ensure_ascii=False)
