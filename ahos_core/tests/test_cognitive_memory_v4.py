"""V4 G003-G005: uzun vadeli/meta/paylaşılan hafıza, çoklu plan, üstbiliş."""
from __future__ import annotations

import json

import pytest

from ahos import cognitive_memory as cm


def test_long_term_survives_save_and_load(tmp_path):
    profile = cm.load(tmp_path, "w-1", "software")
    cm.remember_long_term(profile, mission_id="m-1", plan_type="simple_edit",
                          ok=True, department="software")
    cm.remember_long_term(profile, mission_id="m-2", plan_type="simple_edit",
                          ok=False, department="software")
    cm.save(tmp_path, profile)

    again = cm.load(tmp_path, "w-1")
    row = again["memory"]["long_term"]["by_plan"]["simple_edit"]
    assert row["ok"] == 1 and row["fail"] == 1
    assert again["memory"]["long_term"]["milestones"][-1]["mission_id"] == "m-2"


def test_old_profile_migrates_lazily(tmp_path):
    profile = cm.new_profile("w-old", "software")
    for key in ("long_term", "shared"):
        profile["memory"].pop(key, None)
    cm.remember_long_term(profile, mission_id="m-9", plan_type="executor", ok=True)
    assert "long_term" in profile["memory"]
    assert profile["memory"]["long_term"]["by_plan"]["executor"]["ok"] == 1


def test_meta_memory_tracks_source_reliability(tmp_path):
    profile = cm.load(tmp_path, "w-2")
    cm.meta_note(profile, "mission_qa", True)
    cm.meta_note(profile, "mission_qa", False)
    row = profile["meta_memory"]["mission_qa"]
    assert row["ok"] == 1 and row["fail"] == 1 and row["reliability"] == 0.5


def test_shared_knowledge_dedupes_verified_and_keeps_proposals(tmp_path):
    first = cm.share_knowledge(tmp_path, department="software", statement="A yöntemi işe yarar",
                               source="mission:m-1", mission_id="m-1", verified=True)
    again = cm.share_knowledge(tmp_path, department="software", statement="A yöntemi işe yarar",
                               source="mission:m-1", mission_id="m-1", verified=True)
    assert first["statement"] == again["statement"]

    cm.share_knowledge(tmp_path, department="software", statement="B önerisi test edilmedi",
                       source="agent", mission_id="m-2", verified=False)
    cm.share_knowledge(tmp_path, department="software", statement="B önerisi test edilmedi",
                       source="agent", mission_id="m-3", verified=False)
    rows = [json.loads(line) for line in
            (tmp_path / "cognition" / "_shared.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 3  # doğrulanmış tek, iki öneri ayrı
    assert profile_shared_count(tmp_path) >= 0


def profile_shared_count(tmp_path):
    profile = cm.load(tmp_path, "w-3")
    cm.share_from_profile(tmp_path, profile, statement="C kuralı", source="mission:m-4",
                          mission_id="m-4", verified=True)
    assert profile["memory"]["shared"][-1]["verified"] is True
    return 1


def test_recall_returns_source_date_and_confidence(tmp_path):
    profile = cm.load(tmp_path, "w-4")
    cm.record_episode(profile, mission_id="m-1", outcome="completed",
                      summary="kabul kapısı doğrulaması", evidence_ok=True)
    cm.learn_semantic(profile, statement="Kabul kapısı geçmeyen iş teslim değildir",
                      source="mission:m-1", mission_id="m-1", verified=True)
    hits = cm.recall(profile, "kabul kapısı", limit=5)
    assert hits and hits[0]["kind"] == "semantic"
    assert hits[0]["confidence"] == 1.0 and hits[0]["source"]


def test_conflict_keeps_both_and_picks_higher_confidence(tmp_path):
    profile = cm.load(tmp_path, "w-5")
    record = cm.resolve_conflict(
        profile,
        existing={"statement": "X", "verified": False, "confidence": 0.4},
        candidate={"statement": "X değil", "verified": True, "confidence": 0.95})
    assert record["winner"]["statement"] == "X değil"
    assert profile["conflicts"][-1]["existing"]["statement"] == "X"


def test_build_plans_requires_three_and_records_rationale(tmp_path):
    profile = cm.load(tmp_path, "w-6")
    with pytest.raises(ValueError):
        cm.build_plans(profile, goal="teslim", candidates=[{"name": "tek"}])

    candidates = [
        {"name": "hizli", "steps": ["yaz", "yayinla"], "risk": 0.6,
         "success_probability": 0.6, "estimated_cost_usd": 0.0,
         "verification": "QA", "evidence_score": 0.5},
        {"name": "guvenli", "steps": ["yaz", "test", "QA"], "risk": 0.1,
         "success_probability": 0.9, "estimated_cost_usd": 0.0,
         "verification": "bağımsız QA", "evidence_score": 0.9},
        {"name": "arastir", "steps": ["kaynak tara", "prototip"], "risk": 0.3,
         "success_probability": 0.5, "estimated_cost_usd": 0.0,
         "verification": "karşılaştırma", "evidence_score": 0.7},
    ]
    result = cm.build_plans(profile, goal="teslim", candidates=candidates)
    assert result["chosen"] == "guvenli"
    assert len(result["options"]) == 3
    for plan in result["options"]:
        for key in ("goal", "steps", "tools", "dependencies", "expected_result",
                    "estimated_cost_usd", "risk", "success_probability",
                    "verification", "alternative", "score"):
            assert key in plan
    assert "skor" in result["rationale"]


def test_assess_task_without_evidence_prefers_research(tmp_path):
    profile = cm.load(tmp_path, "w-7")
    verdict = cm.assess_task(profile, task="yeni API tasarla")
    assert verdict["decision"] == "research" and verdict["qa_required"] is True
    assert verdict["missing_information"]


def test_assess_task_with_failures_prefers_help(tmp_path):
    profile = cm.load(tmp_path, "w-8")
    for index in range(4):
        cm.record_episode(profile, mission_id=f"m-{index}", outcome="blocked",
                          evidence_ok=True)
    verdict = cm.assess_task(profile, task="yeni API tasarla")
    assert verdict["decision"] == "ask_help"
    assert verdict["can_do"] is False and verdict["error_rate"] == 1.0


def test_assess_task_with_proven_success_can_proceed(tmp_path):
    profile = cm.load(tmp_path, "w-9")
    for index in range(10):
        cm.record_episode(profile, mission_id=f"m-{index}", outcome="completed",
                          evidence_ok=True)
    verdict = cm.assess_task(profile, task="benzer API")
    assert verdict["decision"] == "proceed"
    assert verdict["qa_required"] is False
