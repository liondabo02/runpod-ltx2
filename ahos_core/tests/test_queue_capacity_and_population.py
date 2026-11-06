"""Atomic 300-pending admission and automatic post-drain balancing."""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from ahos.autonomous_company import (
    MAX_PENDING_MISSIONS, PersistentMissionQueue, QueueCapacityError,
)
from ahos.initiative import tick as initiative_tick
from ahos.mind_feedback import flush_plan_queue
from ahos.mission_orchestrator import MissionResult, MissionStatus
from ahos.queue_budget import can_generate, pending_count
from ahos.queue_drain import drain


def _seed(queue, n):
    with queue._connect() as conn:
        conn.executemany(
            "INSERT INTO missions (mission_id, objective, primary_department,"
            "status, attempts, max_attempts, next_attempt_at, created_at, updated_at)"
            " VALUES (?, ?, ?, 'pending', 0, 1, 0, ?, ?)",
            [(f"seed-{i:04d}", "test-only objective", "software",
              f"2026-01-01T00:00:{i%60:02d}", f"2026-01-01T00:00:{i%60:02d}")
             for i in range(n)],
        )


def _add(queue, ident):
    return queue.enqueue(mission_id=ident, objective="test new work",
                         primary_department="software")


def test_atomic_capacity_preserves_pending_and_never_drops_existing(tmp_path):
    queue = PersistentMissionQueue(tmp_path / "company-service.db")
    _seed(queue, MAX_PENDING_MISSIONS - 1)
    assert pending_count(tmp_path) == 299

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(_add, queue, f"new-{n}") for n in range(2)]
        results = []
        for f in futures:
            try:
                results.append(f.result())
            except QueueCapacityError:
                results.append("paused")

    assert sum(1 for r in results if r == "paused") == 1
    assert pending_count(tmp_path) == MAX_PENDING_MISSIONS
    assert len(queue.list()) == MAX_PENDING_MISSIONS
    with pytest.raises(QueueCapacityError):
        _add(queue, "after-full")
    assert queue.get("after-full") is None


def test_replace_pending_not_double_counted_but_blocked_requeue_is_gated(tmp_path):
    queue = PersistentMissionQueue(tmp_path / "company-service.db")
    _seed(queue, 300)
    old = queue.get("seed-0000")
    queue.enqueue(mission_id=old.mission_id, objective="updated",
                  primary_department="software", replace_existing=True)
    assert pending_count(tmp_path) == 300
    with queue._connect() as conn:
        conn.execute("INSERT INTO missions (mission_id,objective,primary_department,"
                     "status,attempts,max_attempts,next_attempt_at,created_at,updated_at)"
                     " VALUES ('blocked-one','old','software','blocked',0,1,0,'a','a')")
    with pytest.raises(QueueCapacityError):
        queue.enqueue(mission_id="blocked-one", objective="reopen",
                      primary_department="software", replace_existing=True)
    assert queue.get("blocked-one").status.value == "blocked"


def test_sqlite_beats_stale_initiative_stats(tmp_path):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    queue = PersistentMissionQueue(runtime / "company-service.db")
    _seed(queue, MAX_PENDING_MISSIONS)
    (runtime / "mission-stats.json").write_text(json.dumps({"pending": 0}),
                                                  encoding="utf-8")
    config = tmp_path / "config"
    config.mkdir()
    (config / "training-report.json").write_text(
        json.dumps({"departments": 1, "workers": 1,
                    "results": [{"department": "software", "score": 30}]}),
        encoding="utf-8")
    report = initiative_tick(runtime, [{"department_id": "software"}])
    assert report["created"] == 0
    entry = json.loads((runtime / "initiative.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert entry["pending_source"] == "sqlite"
    assert entry["pending"] == MAX_PENDING_MISSIONS
    assert entry["queue_backpressure"] is True


def test_plan_queue_waits_under_pressure_then_draining_resumes(tmp_path):
    runtime = tmp_path
    queue = PersistentMissionQueue(runtime / "company-service.db")
    _seed(queue, 240)
    plan_path = runtime / "minds" / "plan-queue.jsonl"
    plan_path.parent.mkdir()
    plan_path.write_text(json.dumps({
        "state": "pending", "department": "software",
        "worker": "software-manager", "action": "review backlog",
    }), encoding="utf-8")

    paused = flush_plan_queue(runtime, limit=1)
    assert paused["created"] == 0 and paused["deferred"] == 1
    assert json.loads(plan_path.read_text(encoding="utf-8"))["state"] == "pending"

    class Console:
        runtime_dir = runtime
        book = SimpleNamespace(get=lambda department:
                               SimpleNamespace(department_id=department))

        def _project_for_department(self, department):
            return None

        def _execute(self, spec, objective, mission_id):
            return MissionResult(mission_id=mission_id, objective=objective,
                                 manager_id="software-manager", steps=(),
                                 status=MissionStatus.BLOCKED,
                                 reason="test-only: no verified delivery")

        def _record(self, mission_id, owner, result):
            queue.block(mission_id, owner=owner, result=result)

    result = drain(Console(), limit=1)
    assert len(result["executed"]) == 1
    assert result["balance"]["auto_resumed_plans"] == 1
    assert pending_count(runtime) == 240
    assert queue.get("seed-0000").status.value == "blocked"
    assert json.loads(plan_path.read_text(encoding="utf-8"))["state"] == "queued"
    assert can_generate(runtime)["allowed"] is False


def test_worker_seed_and_round_robin_coverage_with_realistic_roster(tmp_path):
    from ahos.worker_mind import bootstrap, tick, load

    runtime = tmp_path / "runtime"
    runtime.mkdir()
    departments = [{"department_id": "creative", "workers": [
        {"worker_id": f"w-{i}", "role": "researcher", "skills": ["analysis"]}
        for i in range(81)
    ]}]
    (runtime / "departments.json").write_text(
        json.dumps({"departments": departments}), encoding="utf-8")

    first = bootstrap(runtime, departments)
    assert first == {"rostered": 81, "initialized": 81}
    assert bootstrap(runtime, departments)["initialized"] == 0
    seen = set()
    for _ in range(9):
        report = tick(runtime, [], limit=10)
        seen.update(report["cycled_workers"])
    assert len(seen) == 81
    assert len({p.stem for p in (runtime / "minds").glob("w-*.json")}) == 81
    assert all(load(runtime, wid).success_rate == 0.0 for wid in seen)
    assert load(runtime, "w-80").self_model["operational_state"]["simulated"] is True



def test_direct_sql_writers_cannot_exceed_capacity(tmp_path):
    import sqlite3

    queue = PersistentMissionQueue(tmp_path / "company-service.db")
    _seed(queue, MAX_PENDING_MISSIONS)
    with pytest.raises(sqlite3.IntegrityError, match="pending_capacity_reached"):
        with queue._connect() as conn:
            conn.execute(
                "INSERT INTO missions (mission_id,objective,primary_department,"
                "status,attempts,max_attempts,next_attempt_at,created_at,updated_at)"
                " VALUES ('direct-extra','x','software','pending',0,1,0,'a','a')"
            )
    with queue._connect() as conn:
        conn.execute(
            "INSERT INTO missions (mission_id,objective,primary_department,"
            "status,attempts,max_attempts,next_attempt_at,created_at,updated_at)"
            " VALUES ('running-one','x','software','running',0,1,0,'a','a')"
        )
    with pytest.raises(sqlite3.IntegrityError, match="pending_capacity_reached"):
        with queue._connect() as conn:
            conn.execute(
                "UPDATE missions SET status='pending' WHERE mission_id='running-one'"
            )
    assert pending_count(tmp_path) == MAX_PENDING_MISSIONS
    assert queue.get("running-one").status.value == "running"


def test_background_commune_rotates_real_departments_without_spamming(tmp_path):
    from ahos.commune import converse, recent

    runtime = tmp_path
    departments = [{"department_id": f"dept-{i}", "workers": [
        {"worker_id": f"d{i}-a"}, {"worker_id": f"d{i}-b"}]}
        for i in range(6)]
    (runtime / "departments.json").write_text(
        json.dumps({"departments": departments}), encoding="utf-8")
    first = converse(runtime, [], rounds=1, seed=5)
    assert first["pairs"] == 4 and first["messages"] == 8
    assert converse(runtime, [], rounds=1)["reason"] == "cooldown"
    cursor = runtime / "minds" / ".commune-cadence.json"
    state = json.loads(cursor.read_text(encoding="utf-8"))
    state["last_at"] = 0
    cursor.write_text(json.dumps(state), encoding="utf-8")
    second = converse(runtime, [], rounds=1, seed=5)
    assert second["pairs"] == 4
    covered = {row["department"] for row in recent(runtime, limit=20)}
    assert covered == {f"dept-{i}" for i in range(6)}
    assert not any(path.stem.startswith("d") for path in (runtime / "minds").glob("*.json"))



def test_corrupt_worker_memory_is_never_reset_or_overwritten(tmp_path):
    from ahos.worker_mind import bootstrap, tick, load, save, Mind

    department = [{"department_id": "software",
                   "workers": [{"worker_id": "agent-one"}]}]
    bootstrap(tmp_path, department)
    stored = tmp_path / "minds" / "agent-one.json"
    original = b'{broken-valuable-unreadable}'
    stored.write_bytes(original)
    with pytest.raises(ValueError, match="original preserved"):
        load(tmp_path, "agent-one")
    result = tick(tmp_path, department, limit=1, seed=0)
    assert result["memory_errors"] == ["agent-one"]
    assert stored.read_bytes() == original
    valid = Mind(worker_id="agent-two", department="software")
    saved = save(tmp_path, valid)
    assert json.loads(saved.read_text(encoding="utf-8"))["worker_id"] == "agent-two"
    assert not list((tmp_path / "minds").glob("*.tmp"))



def test_memory_overflow_is_archived_before_active_window_moves(tmp_path):
    from ahos.worker_mind import MAX_EVENTS, Mind, load, save

    mind = Mind(worker_id="history-agent", department="software",
                events=[{"kind": "mission", "ok": bool(i % 2), "id": i}
                        for i in range(MAX_EVENTS + 3)])
    path = save(tmp_path, mind)
    active = json.loads(path.read_text(encoding="utf-8"))
    assert len(active["events"]) == MAX_EVENTS
    assert active["events"][0]["id"] == 3
    archive = tmp_path / "minds" / "archive" / "history-agent.jsonl"
    archived = [json.loads(line) for line in archive.read_text(encoding="utf-8").splitlines()]
    assert [row["id"] for row in archived] == [0, 1, 2]

    remembered = load(tmp_path, "history-agent")
    remembered.events.append({"kind": "mission", "ok": True, "id": MAX_EVENTS + 3})
    save(tmp_path, remembered)
    archived_after = [json.loads(line) for line in archive.read_text(encoding="utf-8").splitlines()]
    assert [row["id"] for row in archived_after] == [0, 1, 2, 3]
