"""Bilişsel hafıza, üstbiliş, işlevsel duygu ve kolektif zeka testleri."""
from __future__ import annotations

import json

import pytest

from ahos import cognitive_memory as cm


def test_profile_persists_and_existing_data_is_not_reset(tmp_path):
    profile = cm.load(tmp_path, "w-1", "software")
    profile["memory"]["working"] = {"mission_id": "m-1", "objective": "x"}
    cm.save(tmp_path, profile)

    loaded = cm.load(tmp_path, "w-1", "software")
    assert loaded["worker_id"] == "w-1"
    assert loaded["memory"]["working"]["mission_id"] == "m-1"
    assert loaded["evidence"]["status"] == "no_verified_evidence"


def test_unverified_semantic_memory_is_rejected(tmp_path):
    profile = cm.load(tmp_path, "w-2")
    with pytest.raises(ValueError):
        cm.learn_semantic(profile, statement="model iyidir", source="tahmin",
                          verified=False)
    entry = cm.learn_semantic(profile, statement="QA geçen iş teslim sayılır",
                              source="mission:m-9", mission_id="m-9", verified=True)
    assert entry["verified"] is True


def test_procedural_memory_only_counts_observed_outcomes(tmp_path):
    profile = cm.load(tmp_path, "w-3")
    cm.learn_procedural(profile, plan_type="simple_edit", ok=True, steps=["apply", "verify"])
    cm.learn_procedural(profile, plan_type="simple_edit", ok=False)
    row = profile["memory"]["procedural"][0]
    assert row["ok"] == 1 and row["fail"] == 1 and row["rate"] == 0.5
    assert row["steps"] == ["apply", "verify"]


def test_reflection_without_evidence_says_so(tmp_path):
    profile = cm.load(tmp_path, "w-4")
    entry = cm.reflect(profile, mission_id="m-4", ok=True, plan_type="executor",
                       evidence_ok=False)
    assert "kanıt yok" in entry["lesson"]
    assert entry["verified"] is False

    verified = cm.reflect(profile, mission_id="m-5", ok=True, plan_type="executor",
                          evidence_ok=True)
    assert "doğrulandı" in verified["lesson"] and verified["verified"] is True


def test_metacognition_is_derived_from_verified_missions(tmp_path):
    profile = cm.load(tmp_path, "w-5")
    cm.record_episode(profile, mission_id="a", outcome="completed", evidence_ok=True)
    cm.record_episode(profile, mission_id="b", outcome="blocked", evidence_ok=True)
    cm.record_episode(profile, mission_id="c", outcome="completed", evidence_ok=False)
    meta = cm.metacognition(profile)
    assert meta["samples"] == 2          # kanıtsız olay sayılmaz
    assert meta["observed_rate"] == 0.5
    assert 0.0 <= meta["confidence"] <= 1.0
    assert meta["error_rate"] == 0.5


def test_emotion_is_bounded_and_cannot_change_authority(tmp_path):
    profile = cm.load(tmp_path, "w-6")
    state = cm.emotion(profile, pending=240, idle=False)
    assert all(0.0 <= value <= 1.0 for value in state.values())
    priority = cm.emotion_priority(profile, pending=240, idle=False)
    assert priority["authority_effect"] == "none"
    assert priority["spend_effect"] == "none"
    assert priority["mode"] == "drain_backlog"
    idle = cm.emotion_priority(cm.load(tmp_path, "w-7"), pending=0, idle=True)
    assert idle["mode"] == "explore_and_learn"


def test_collective_expertise_handoff_review_and_mentorship(tmp_path):
    departments = [{"department_id": "software", "workers": [
        {"worker_id": "dev-a", "capabilities": ["python", "testing"]},
        {"worker_id": "dev-b", "capabilities": ["python"]},
    ]}]
    a = cm.load(tmp_path, "dev-a", "software")
    b = cm.load(tmp_path, "dev-b", "software")
    cm.learn_procedural(a, plan_type="simple_edit", ok=True)
    cm.learn_procedural(b, plan_type="simple_edit", ok=False)
    cm.save(tmp_path, a)
    cm.save(tmp_path, b)

    index = cm.expert_index(tmp_path, departments)
    assert index["python"][0]["worker"] == "dev-a"      # daha yüksek oran önce
    assert cm.find_expert(tmp_path, "python", exclude=["dev-a"])[0]["worker"] == "dev-b"

    cm.handoff(tmp_path, mission_id="m-1", from_worker="dev-b", to_worker="dev-a",
               reason="expertise", evidence_ok=True)
    cm.peer_review(tmp_path, mission_id="m-1", reviewer="dev-a", verdict="pass",
                   note="verified", evidence_ok=True)
    with pytest.raises(ValueError):
        cm.peer_review(tmp_path, mission_id="m-2", reviewer="dev-a", verdict="bogus",
                       note="")
    pairs = cm.mentor_pairs(tmp_path, departments)
    assert pairs and pairs[0]["mentor"] == "dev-a" and pairs[0]["mentee"] == "dev-b"

    rows = [json.loads(line) for line in
            (tmp_path / "cognition" / "_collective.jsonl").read_text(encoding="utf-8").splitlines()]
    assert {row["kind"] for row in rows} == {"handoff", "peer_review"}


def test_corrupt_profile_is_preserved_not_overwritten(tmp_path):
    path = tmp_path / "cognition" / "broken.json"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"{not-json")
    with pytest.raises(ValueError):
        cm.load(tmp_path, "broken")
    assert path.read_bytes() == b"{not-json"
