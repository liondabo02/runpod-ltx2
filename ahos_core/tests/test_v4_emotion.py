"""G013: 9 boyutlu işlevsel duygu politikası ve karar etkisi."""
from __future__ import annotations

from ahos import cognitive_memory as cm

EMOTION_DIMENSIONS = ("curiosity", "learning_drive", "confidence", "caution",
                      "workload", "collaboration", "recovery", "patience",
                      "quality_drive")


def _episodes(profile, outcome, count):
    for index in range(count):
        cm.record_episode(profile, mission_id=f"{outcome}-{index}",
                          outcome=outcome, evidence_ok=True)


def test_nine_dimensions_present_and_bounded(tmp_path):
    profile = cm.load(tmp_path, "w-1")
    state = cm.emotion(profile, pending=0, idle=True)
    for key in EMOTION_DIMENSIONS:
        assert key in state, key
        assert 0.0 <= state[key] <= 1.0
    priority = cm.emotion_priority(profile, pending=0, idle=True)
    assert priority["authority_effect"] == "none"
    assert priority["spend_effect"] == "none"
    assert priority["mode"] == "explore_and_learn"
    assert state["learning_drive"] > 0.6


def test_failure_and_workload_change_policy(tmp_path):
    failing = cm.load(tmp_path, "w-2")
    _episodes(failing, "blocked", 10)
    state = cm.emotion(failing, pending=120, idle=False)
    assert state["caution"] >= 0.8
    assert state["help_seeking"] >= 0.7
    assert cm.emotion_priority(failing, pending=120, idle=False)["mode"] == "ask_for_help"

    overloaded = cm.load(tmp_path, "w-3")
    assert cm.emotion_priority(overloaded, pending=240, idle=False)["mode"] == "drain_backlog"


def test_success_changes_policy_and_recovery(tmp_path):
    profile = cm.load(tmp_path, "w-4")
    _episodes(profile, "completed", 10)
    state = cm.emotion(profile, pending=0, idle=False, last_outcome="completed")
    assert state["confidence"] > 0.9
    assert state["caution"] <= 0.25
    assert state["recovery"] == 1.0
    assert state["patience"] >= 0.6
    assert cm.emotion_priority(profile, pending=0, idle=False)["mode"] == "deliver_verified_work"

    after_failure = cm.emotion(profile, pending=0, idle=False, last_outcome="blocked")
    assert after_failure["recovery"] == 0.15


def test_emotion_state_actually_changes_work_decision(tmp_path):
    research = cm.load(tmp_path, "w-5")
    careful = cm.load(tmp_path, "w-6")
    _episodes(careful, "blocked", 10)
    # Kanıtsız işçi araştırmaya, hatalı işçi doğrulamaya yönelir.
    assert cm.assess_task(research, task="yeni iş")["decision"] == "research"
    assert cm.assess_task(careful, task="yeni iş")["decision"] == "ask_help"
    assert cm.emotion(research, pending=0, idle=True)["curiosity"] > \
        cm.emotion(careful, pending=0, idle=True)["curiosity"]
