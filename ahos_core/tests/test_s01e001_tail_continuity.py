"""S04–S05 kuyruk ayrılışı/arama sürekliliği testleri."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import validate_s01e001_v2 as validator  # noqa: E402

EPISODE = json.loads((ROOT / "studio" / "s01e001" / "episode-v2.json").read_text(encoding="utf-8"))
SCENES = {scene["scene_id"]: scene for scene in EPISODE["scenes"]}


def test_six_strips_and_landing_distribution():
    tail = EPISODE["tail_consistency"]
    assert tail["strip_count"] == 6
    assert len(tail["strips"]) == 6
    assert len({strip["color"] for strip in tail["strips"]}) == 6
    assert Counter(strip["landing"] for strip in tail["strips"]) == {
        "piknik örtüsü": 3, "papatya yanındaki çimen": 2, "alçak çalı": 1}


def test_s04_shows_all_six_separating():
    text = " ".join(beat["action"] for beat in SCENES["V2-S04"]["beats"]).lower()
    for color in ("kırmızı", "sarı", "mavi", "yeşil", "turuncu", "mor"):
        assert color in text


def test_s05_finds_exactly_what_s04_dropped():
    text = " ".join(beat["action"] for beat in SCENES["V2-S05"]["beats"]).lower()
    for color in ("kırmızı", "sarı", "mavi", "yeşil", "turuncu", "mor"):
        assert color in text
    assert "eksik" not in text
    assert "altı" in SCENES["V2-S05"]["beats"][-1]["action"].lower()


def test_repair_uses_three_then_remaining_three():
    assert "üç" in SCENES["V2-S07"]["action"].lower()
    assert "kalan üç" in SCENES["V2-S08"]["action"].lower()


def test_validator_still_passes():
    opening = json.loads((ROOT / "studio" / "s01e001" / "episode-open-30s-v2.json")
                         .read_text(encoding="utf-8"))
    assert validator.validate(EPISODE, opening) == []
