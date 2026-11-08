"""S01E001 paketi: 480 sn senaryo, 30 sn çekim listesi, ses envanteri."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import validate_s01e001 as validator  # noqa: E402


def _load(name: str) -> dict:
    return json.loads((ROOT / "studio" / "s01e001" / name).read_text(encoding="utf-8"))


def test_real_package_passes_all_checks():
    assert validator.validate(_load("episode.json"), _load("shotlist-30s.json")) == []


def test_episode_is_exactly_480_seconds_and_contiguous():
    episode = _load("episode.json")
    assert sum(scene["duration_seconds"] for scene in episode["scenes"]) == 480
    assert episode["target_duration_seconds"] == 480


def test_kaan_lines_never_become_sentences():
    episode = _load("episode.json")
    for scene in episode["scenes"]:
        for line in scene["dialogue"]:
            if line["speaker"] == "kaan":
                assert len(line["text"].split()) <= 2, line


def test_validator_rejects_long_kaan_line():
    episode = _load("episode.json")
    episode["scenes"][0]["dialogue"][1]["text"] = "Ben de uçurtmayı uçurmak istiyorum"
    problems = validator.validate(episode, _load("shotlist-30s.json"))
    assert any("Kaan" in item for item in problems)


def test_validator_rejects_wrong_duration():
    episode = _load("episode.json")
    episode["scenes"][0]["duration_seconds"] += 1
    problems = validator.validate(episode, _load("shotlist-30s.json"))
    assert any("480" in item for item in problems)


def test_voice_inventory_is_honest_about_approval():
    inventory = _load("voice-inventory.json")
    assert inventory["approval"] == "NOT_EVALUATED"
    assert {item["character_id"] for item in inventory["assets"]} == {"aden", "kaan", "esra", "harun"}
    assert all(item["exists"] for item in inventory["assets"])
    assert sum(inventory["episode_line_counts"].values()) == 38
