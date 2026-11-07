"""V5 GÖREV 010: departman beyni gerçek kayıtlarla eşleşmeli."""
from __future__ import annotations

import json
import sqlite3

from ahos import department_brain


def _runtime(tmp_path):
    runtime = tmp_path / "runtime"
    (runtime / "cognition").mkdir(parents=True)
    (runtime / "departments.json").write_text(json.dumps({"departments": [
        {"department_id": "creative", "name": "Creative", "workers": [
            {"worker_id": "c-mgr", "role": "manager", "capabilities": ["story"]},
            {"worker_id": "c-art", "role": "specialist", "capabilities": ["art"]},
        ]},
        {"department_id": "quality", "name": "Quality", "workers": [
            {"worker_id": "q-qa", "role": "qa", "capabilities": ["qa"]},
        ]},
    ]}), encoding="utf-8")
    db = sqlite3.connect(runtime / "company-service.db")
    db.execute("create table missions (mission_id text primary key, objective text, "
               "status text, updated_at text, last_error text, result_json text)")
    db.execute("insert into missions values (?,?,?,?,?,?)",
               ("m-1", "pilot", "completed", "2026-11-07T10:00:00", None,
                json.dumps({"primary_department": "creative",
                            "steps": [{"department": "creative"},
                                      {"department": "quality"}]})))
    db.execute("insert into missions values (?,?,?,?,?,?)",
               ("m-2", "bozuk", "blocked", "2026-11-07T11:00:00", "timeout", "{}"))
    db.commit()
    db.close()
    (runtime / "cognition" / "_shared.jsonl").write_text(json.dumps({
        "department": "creative", "verified": True, "statement": "kural"}) + "\n",
        encoding="utf-8")
    root = tmp_path / "deliverables" / "TEST-1"
    root.mkdir(parents=True)
    (root / "manifest.json").write_text(json.dumps({
        "delivery_id": "TEST-1",
        "contributors": [{"department": "creative", "worker": "c-art",
                          "task": "frames", "status": "completed",
                          "verified_by": "q-qa"}]}), encoding="utf-8")
    return runtime


def test_department_brain_matches_records(tmp_path):
    runtime = _runtime(tmp_path)
    brain = department_brain.snapshot(runtime, "creative")
    assert brain["manager"] == "c-mgr"
    assert brain["workers"] == 2
    assert brain["capability_map"] == ["art", "story"]
    assert brain["missions"] == 1
    assert brain["blocked"] >= 0
    assert brain["delivered_tasks"] == 1
    assert brain["shared_facts"] == 1
    assert brain["dependencies"] == ["quality"]


def test_all_brains_returns_17_capable(tmp_path):
    runtime = _runtime(tmp_path)
    brains = department_brain.all_brains(runtime)
    assert len(brains) == 2
    assert {row["department_id"] for row in brains} == {"creative", "quality"}
