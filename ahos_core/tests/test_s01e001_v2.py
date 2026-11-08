"""S01E001 v2: kronoloji, açılış uyumu, Kaan dili ve v1/POC koruması."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import validate_s01e001_v2 as validator  # noqa: E402


def load(name: str) -> dict:
    return json.loads((ROOT / "studio" / "s01e001" / name).read_text(encoding="utf-8"))


def test_real_v2_package_passes():
    assert validator.validate(load("episode-v2.json"), load("episode-open-30s-v2.json")) == []


def test_v1_is_preserved():
    v1 = load("episode.json")
    assert len(v1["scenes"]) == 12
    assert sum(s["duration_seconds"] for s in v1["scenes"]) == 480


def test_independent_poc_is_untouched():
    pilot = json.loads((ROOT / "workflows" / "S01E001-pilot-30s-plan.json").read_text(encoding="utf-8"))
    assert pilot["status"] == "PROPOSED_NOT_OWNER_APPROVED"
    assert pilot["target_duration_seconds"] == 30


def test_opening_events_must_match_first_scene():
    opening = load("episode-open-30s-v2.json")
    opening["shots"][0]["event"] = "wrong_event"
    problems = validator.validate(load("episode-v2.json"), opening)
    assert any("açılış olayları" in item for item in problems)


def test_chronology_must_not_reorder_repair_before_search():
    episode = load("episode-v2.json")
    episode["events"][4], episode["events"][5] = episode["events"][5], episode["events"][4]
    problems = validator.validate(episode, load("episode-open-30s-v2.json"))
    assert any("olay sırası" in item or "kronoloji" in item for item in problems)


def test_kaan_cannot_use_other_words():
    episode = load("episode-v2.json")
    episode["scenes"][0]["dialogue"][0]["text"] = "Nerede?"
    problems = validator.validate(episode, load("episode-open-30s-v2.json"))
    assert any("Kaan sözlük" in item for item in problems)


def test_every_beat_is_5_to_10_seconds():
    episode = load("episode-v2.json")
    episode["scenes"][0]["beats"][0]["duration_seconds"] = 4
    problems = validator.validate(episode, load("episode-open-30s-v2.json"))
    assert any("5-10 dışı" in item for item in problems)
