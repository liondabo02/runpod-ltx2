"""Regression tests for bounded, fair and evidence-grounded idle study."""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone

from ahos.self_learning import progress, tick


def _roster(runtime, n: int = 81):
    departments = [{
        "department_id": "software",
        "workers": [
            {"worker_id": f"worker-{i:03d}", "role": "software_engineer"}
            for i in range(n)
        ],
    }]
    (runtime / "departments.json").write_text(
        json.dumps({"departments": departments}), encoding="utf-8"
    )
    return departments


def test_idle_study_round_robin_reaches_all_81_workers(tmp_path):
    _roster(tmp_path)
    seen = set()
    for _ in range(14):
        report = tick(tmp_path, limit=6)
        assert report["count"] <= 6
        seen.update(report["studied"])
    assert len(seen) == 81
    assert set(seen) == {f"worker-{i:03d}" for i in range(81)}
    log = tmp_path / "learning" / "software.jsonl"
    lessons = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert len(lessons) == 84  # 14 bounded cycles * 6 lessons; 81 distinct workers
    assert all(entry["verified_skill_gain"] is False for entry in lessons)
    assert all(entry["learning_mode"] == "deterministic_micro_lesson"
               for entry in lessons)
    assert progress(tmp_path)["software"] == 84


def test_active_worker_is_not_mistaken_for_idle_and_old_worker_can_study(tmp_path):
    _roster(tmp_path, n=3)
    new = datetime.fromtimestamp(time.time(), timezone.utc).isoformat()
    old = datetime.fromtimestamp(time.time() - 4_000, timezone.utc).isoformat()
    activity = [
        {"at": new, "worker_id": "worker-000"},
        {"at": old, "worker_id": "worker-001"},
    ]
    (tmp_path / "worker-metrics.jsonl").write_text(
        "\n".join(json.dumps(row) for row in activity) + "\n",
        encoding="utf-8",
    )
    report = tick(tmp_path, limit=3)
    assert report["studied"] == ["worker-001", "worker-002"]
    assert report["skipped_recently_active"] == 1
    assert report["rostered"] == 3
    assert "worker-000" not in report["studied"]


def test_idle_study_does_not_enqueue_missions(tmp_path):
    _roster(tmp_path, n=20)
    from ahos.autonomous_company import PersistentMissionQueue
    from ahos.queue_budget import pending_count

    queue = PersistentMissionQueue(tmp_path / "company-service.db")
    queue.enqueue(mission_id="keep", objective="original",
                  primary_department="software")
    before = pending_count(tmp_path)
    result = tick(tmp_path, limit=6)
    assert result["count"] == 6
    assert pending_count(tmp_path) == before == 1
    assert queue.get("keep").objective == "original"


def test_daemon_tick_records_idle_learning_in_state(tmp_path, monkeypatch):
    from ahos import daemon, health_guard, outcome

    _roster(tmp_path, n=4)
    monkeypatch.setattr(health_guard, "check", lambda runtime, fix=False:
                        type("Health", (), {"ok": True, "checks": [], "repairs": []})())
    monkeypatch.setattr(outcome, "adjust", lambda runtime, department:
                        {"scope": "keep"})
    summary = daemon.tick_once(tmp_path, departments=[])
    state = json.loads((tmp_path / "daemon-state.json").read_text(encoding="utf-8"))
    assert state["learning"]["idle_micro_lessons"]["count"] == 4
    assert state["learning"]["idle_micro_lessons"]["rostered"] == 4
    assert state["learning"]["idle_micro_lessons"]["skipped_recently_active"] == 0


def test_hourly_mission_cap_still_runs_idle_lessons(tmp_path, monkeypatch):
    from ahos import daemon
    from ahos.autonomous_company import PersistentMissionQueue

    _roster(tmp_path, n=12)
    queue = PersistentMissionQueue(tmp_path / "company-service.db")
    queue.enqueue(mission_id="keep", objective="existing work",
                  primary_department="software")
    # The hourly quota comes from independently verified completed missions;
    # isolate this branch without fabricating an invalid completion record.
    monkeypatch.setattr(daemon, "_mission_counts", lambda runtime: (1, 1))

    daemon.main([
        "--runtime-dir", str(tmp_path),
        "--once",
        "--missions-per-hour", "1",
    ])
    state = json.loads((tmp_path / "daemon-state.json").read_text(encoding="utf-8"))
    assert state["learning"]["idle_micro_lessons"]["count"] == 6
    assert state["scheduler"]["status"] == "idle"
    assert state["status"] == "stopped"  # one-shot exited
    assert queue.list()[0].mission_id == "keep"
    assert queue.list()[0].status.value == "pending"
    assert not (tmp_path / "daemon.pid").exists()
