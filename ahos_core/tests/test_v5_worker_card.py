"""V5 GÖREV 019: işçi kartı gerçek kayıtlarla eşleşmeli, özel veri gizli."""
from __future__ import annotations

import json

from ahos import cognitive_memory as cm, worker_card


def _runtime(tmp_path):
    runtime = tmp_path / "runtime"
    (runtime / "minds").mkdir(parents=True)
    (runtime / "departments.json").write_text(json.dumps({"departments": [
        {"department_id": "creative", "workers": [
            {"worker_id": "c-1", "name": "Sanatçı", "role": "specialist",
             "capabilities": ["art", "story"]}]}]}), encoding="utf-8")
    profile = cm.load(runtime, "c-1", "creative")
    cm.record_episode(profile, mission_id="m-1", outcome="completed", evidence_ok=True)
    cm.record_episode(profile, mission_id="m-2", outcome="completed", evidence_ok=True)
    cm.learn_procedural(profile, plan_type="storyboard", ok=True)
    cm.learn_semantic(profile, statement="Renk paleti sabit", source="qa",
                      mission_id="m-1", verified=True)
    cm.remember_error(profile, mission_id="m-2", cause="timeout", evidence_ok=True)
    cm.remember_collaboration(profile, mission_id="m-2", helper="q-qa",
                              skill="qa", outcome="geçti", evidence_ok=True)
    cm.set_working(profile, mission_id="m-3", objective="yeni sahne")
    cm.save(runtime, profile)
    (runtime / "minds" / "c-1.json").write_text(json.dumps({
        "events": [{"at": "2026-11-07T10:00:00", "kind": "mission"}]}), encoding="utf-8")
    root = tmp_path / "deliverables" / "D-1"
    root.mkdir(parents=True)
    (root / "manifest.json").write_text(json.dumps({
        "delivery_id": "D-1", "contributors": [
            {"worker": "c-1", "task": "frames", "status": "completed"}]}),
        encoding="utf-8")
    return runtime


def test_card_matches_real_records(tmp_path):
    runtime = _runtime(tmp_path)
    card = worker_card.card(runtime, "c-1")
    assert card["name"] == "Sanatçı" and card["department"] == "creative"
    assert card["current_task"] == "yeni sahne"
    assert card["verified_successes"] == 2
    assert card["learned_methods"] == 1 and card["semantic_facts"] == 1
    assert card["last_error"] == "timeout"
    assert card["last_collaboration"] == "q-qa"
    assert card["artifacts"][0]["delivery_id"] == "D-1"
    assert card["private_memory_hidden"] is True
    assert "private" not in card


def test_private_memory_only_when_allowed(tmp_path):
    runtime = _runtime(tmp_path)
    card = worker_card.card(runtime, "c-1", include_private=True)
    assert card["private_memory_hidden"] is False
    assert card["private"]["semantic"][0]["statement"]
