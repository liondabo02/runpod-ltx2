"""V5 GÖREV 001-002: 10 katmanlı hafıza + kayıt meta verisi + geri çağırma."""
from __future__ import annotations

import json

from ahos import cognitive_memory as cm

LAYERS = ("working", "episodic", "semantic", "procedural", "long_term", "shared",
          "task_context", "error_memory", "collaboration_memory")

META = ("memory_id", "worker_id", "mission_id", "source", "timestamp",
        "confidence", "verification_status", "content_hash", "version")


def _profile(tmp_path):
    return cm.load(tmp_path, "w-1", "software")


def test_ten_layers_exist_and_migrate(tmp_path):
    profile = _profile(tmp_path)
    for layer in LAYERS:
        assert layer in profile["memory"], layer
    legacy = cm.new_profile("w-legacy")
    for key in ("task_context", "error_memory", "collaboration_memory"):
        legacy["memory"].pop(key)
    path = tmp_path / "cognition" / "w-legacy.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(legacy), encoding="utf-8")
    again = cm.load(tmp_path, "w-legacy")
    for key in ("task_context", "error_memory", "collaboration_memory"):
        assert key in again["memory"]


def test_every_record_carries_metadata(tmp_path):
    profile = _profile(tmp_path)
    episode = cm.record_episode(profile, mission_id="m-1", outcome="completed",
                                summary="kabul testi geçti", evidence_ok=True)
    semantic = cm.learn_semantic(profile, statement="Kanıtsız iş teslim değildir",
                                 source="qa", mission_id="m-1", verified=True)
    procedural = cm.learn_procedural(profile, plan_type="executor", ok=True)
    error = cm.remember_error(profile, mission_id="m-2", cause="timeout",
                              fix="süreyi artır", evidence_ok=True)
    collab = cm.remember_collaboration(profile, mission_id="m-3", helper="qa-01",
                                        skill="test", outcome="geçti", evidence_ok=True)
    for record in (episode, semantic, procedural["meta"], error, collab):
        for key in META:
            assert key in record, (key, record)
        assert record["worker_id"] == "w-1"
        assert record["version"] == 1
        assert len(record["content_hash"]) == 64


def test_content_hash_is_content_bound(tmp_path):
    profile = _profile(tmp_path)
    first = cm.remember_error(profile, mission_id="m-1", cause="timeout")
    second = cm.remember_error(profile, mission_id="m-2", cause="timeout")
    third = cm.remember_error(profile, mission_id="m-3", cause="lock")
    assert first["content_hash"] == second["content_hash"]
    assert first["content_hash"] != third["content_hash"]
    assert first["memory_id"] != second["memory_id"]


def test_task_context_persists(tmp_path):
    profile = _profile(tmp_path)
    context = cm.set_task_context(profile, mission_id="m-9", dependencies=["m-8"],
                                  status="waiting_dependency", notes="veri bekliyor")
    assert context["memory_id"] and context["mission_id"] == "m-9"
    cm.save(tmp_path, profile)
    again = cm.load(tmp_path, "w-1")
    assert again["memory"]["task_context"]["status"] == "waiting_dependency"
    assert again["memory"]["task_context"]["dependencies"] == ["m-8"]


def test_recall_prefers_verified_and_reliable(tmp_path):
    profile = _profile(tmp_path)
    cm.record_episode(profile, mission_id="m-1", outcome="completed",
                      summary="kabul kapısı doğrulaması", evidence_ok=False)
    cm.learn_semantic(profile, statement="Kabul kapısı doğrulaması zorunludur",
                      source="qa", mission_id="m-2", verified=True)
    hits = cm.recall_memory(profile, "kabul kapısı", limit=5)
    assert hits and hits[0]["kind"] == "semantic"
    assert hits[0]["verification_status"] == "verified"
    assert hits[0]["memory_id"]

    # aynı içerik, farklı kaynak güvenilirliği → daha güvenilir kaynak öne geçer
    cm.meta_note(profile, "qa", True)
    reliable = cm.recall_memory(profile, "kabul kapısı", limit=5)[0]
    assert reliable["source"] == "qa" and reliable["score"] > 0


def test_error_memory_is_capped(tmp_path):
    profile = _profile(tmp_path)
    for index in range(45):
        cm.remember_error(profile, mission_id=f"m-{index}", cause="timeout")
    assert len(profile["memory"]["error_memory"]) == cm.CAPS["error"]
