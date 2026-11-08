"""G019 testleri: CEO Intelligence Dashboard gerçek kayıtlarla eşleşmeli."""
from __future__ import annotations

import json
import sqlite3

from ahos import cognitive_memory as cm
from ahos import intelligence, owner_auth
from ahos.autonomous_company import PersistentMissionQueue
from ahos.mission_orchestrator import MissionResult, MissionStatus


def _runtime(tmp_path):
    runtime = tmp_path / "runtime"
    (runtime / "minds").mkdir(parents=True)
    (runtime / "cognition").mkdir(parents=True)
    (runtime / "owner").mkdir(parents=True)
    (tmp_path / "config").mkdir(parents=True)
    (tmp_path / "config" / "health-report.json").write_text(
        json.dumps({"ok": True}), encoding="utf-8")
    (runtime / "departments.json").write_text(json.dumps({"departments": [
        {"department_id": "software", "workers": [
            {"worker_id": "w-1", "name": "Geliştirici", "role": "specialist",
             "authority_level": "C", "capabilities": ["python", "testing"]},
            {"worker_id": "w-2", "name": "Testçi", "role": "qa",
             "authority_level": "C", "capabilities": ["qa"]},
        ]},
    ]}), encoding="utf-8")
    return runtime


def _seed(runtime):
    queue = PersistentMissionQueue(runtime / "company-service.db")
    queue.enqueue(mission_id="m-1", objective="test", primary_department="software")
    queue.claim_next(owner="qa", lease_seconds=30)
    queue.complete("m-1", owner="qa", result=MissionResult(
        "m-1", "test", "w-1", MissionStatus.COMPLETED, (), "ok",
        qa_worker_id="w-2"))
    queue.enqueue(mission_id="m-2", objective="bekleyen", primary_department="software")

    (runtime / "minds" / "w-1.json").write_text(json.dumps({
        "worker_id": "w-1", "department": "software",
        "events": [{"kind": "mission", "ok": True, "mission_id": "m-1"}],
        "self_model": {"plan_scores": {"executor": {"ok": 1, "fail": 0, "total_s": 0}}},
    }), encoding="utf-8")
    profile = cm.load(runtime, "w-1", "software")
    cm.record_episode(profile, mission_id="m-1", outcome="completed", evidence_ok=True)
    cm.learn_procedural(profile, plan_type="executor", ok=True)
    cm.save(runtime, profile)
    (runtime / "worker-metrics.jsonl").write_text(json.dumps({
        "worker_id": "w-1", "success": True, "at": "2026-11-07T00:00:00"}) + "\n",
        encoding="utf-8")
    owner_auth.init_owner(runtime, "harun", "correct-horse-battery")
    db = sqlite3.connect(runtime / "owner-approvals.db")
    db.execute("create table approval_requests (request_id text primary key, status text)")
    db.execute("insert into approval_requests values ('r-1','waiting_owner_approval')")
    db.commit()
    db.close()


def test_dashboard_metrics_match_real_records(tmp_path):
    runtime = _runtime(tmp_path)
    _seed(runtime)
    backups = tmp_path / "backups"
    (backups / "vault-1").mkdir(parents=True)

    data = intelligence.snapshot(runtime, backup_root=backups)
    assert data["holding"]["departments"] == 1
    assert data["holding"]["workers"] == 2
    assert data["holding"]["queue"] == {"completed": 1, "pending": 1}
    assert data["holding"]["verified_deliveries"] == 1
    assert data["holding"]["health_ok"] is True
    assert data["security"]["owner_configured"] is True
    assert data["security"]["pending_approvals"] == 1
    assert data["backups"]["vaults"] == 1

    worker = next(row for row in data["workers"] if row["worker"] == "w-1")
    assert worker["runs"] == 1 and worker["run_rate"] == 1.0
    assert worker["best_plan"] == "executor"
    assert worker["learned_methods"] == 1
    assert worker["evidence"] == "verified"

    page = intelligence.render_html(data)
    assert "AHOS CEO Intelligence" in page
    assert "w-1" not in page or "Geliştirici" in page
    assert "pending=1" in page


def test_dashboard_marks_missing_data_without_inventing(tmp_path):
    runtime = _runtime(tmp_path)
    data = intelligence.snapshot(runtime, backup_root=tmp_path / "empty")
    assert data["holding"]["verified_deliveries"] in (None, 0)
    assert data["security"]["owner_configured"] is False
    assert data["backups"]["vaults"] == 0
    assert all(row["runs"] == 0 for row in data["workers"])
    assert all(row["run_rate"] is None for row in data["workers"])
    assert "uydurma" in data["note"]
