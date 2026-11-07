"""Tek karakter kanonu + cinsiyet regresyonu."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ahos_core"))

from ahos.character_canon import CanonError, CharacterCanon  # noqa: E402
from ahos.character_memory import (  # noqa: E402
    CharacterBibleStore, CharacterProfile, CharacterRelationship)

REAL_BIBLE = (ROOT / "control_plane_v2" / "runtime" / "private"
              / "animation-studio" / "character-memory.db")


def _profile(character_id: str, role: str) -> CharacterProfile:
    return CharacterProfile(character_id=character_id, display_name=character_id.title(),
                            canonical_role=role, family_group="test-family",
                            age_stage="about 3 years old")


def test_real_bible_has_16_characters_28_relations_3_facts():
    if not REAL_BIBLE.is_file():
        pytest.skip("private character bible yok (beklenen: yerel makine)")
    canon = CharacterCanon(bible_path=REAL_BIBLE)
    summary = canon.assert_consistent({"characters": 16, "relationships": 28, "canon_facts": 3})
    assert summary["characters"] == 16
    assert summary["gender_known"] == 16
    assert summary["with_audio_en_tr"] == 14
    assert [item for item in canon.conflicts() if item["severity"] == "error"] == []
    categories = summary["conflicts_by_category"]
    assert categories.get("missing_visual_canon") == 14
    assert categories.get("baby_audio_absent") == 2
    assert "missing_audio_asset" not in categories


def test_aden_is_female_in_unified_canon():
    if not REAL_BIBLE.is_file():
        pytest.skip("private character bible yok")
    canon = CharacterCanon(bible_path=REAL_BIBLE)
    aden = next(entry for entry in canon.entries() if entry.character_id == "aden")
    assert aden.gender == "female"
    assert "gender_conflict" not in aden.issues
    assert aden.audio["tr.wav"]["exists"] is True


def test_gender_conflict_is_detected(tmp_path):
    bible = tmp_path / "bible.db"
    store = CharacterBibleStore(bible)
    store.upsert_profile(_profile("aden", "lead_child"), author="test", reason="test",
                         owner_override=True)
    store.upsert_profile(_profile("kaan", "lead_child"), author="test", reason="test",
                         owner_override=True)
    store.add_relationship(CharacterRelationship("aden-sibling_of-kaan", "aden", "kaan",
                                                 "sibling_of"))
    visuals = tmp_path / "characters"
    visuals.mkdir()
    (visuals / "aden.json").write_text(json.dumps(
        {"prompt_fragment": "Aden, a cheerful 3-year-old boy with short hair"}), encoding="utf-8")
    audio = tmp_path / "audio"
    (audio / "aden").mkdir(parents=True)
    (audio / "aden" / "reference-en.wav").write_bytes(b"x")
    (audio / "aden" / "tr.wav").write_bytes(b"x")

    canon = CharacterCanon(bible_path=bible, visuals=visuals, audio=audio)
    aden = next(entry for entry in canon.entries() if entry.character_id == "aden")

    assert "gender_conflict" in aden.issues
    with pytest.raises(CanonError):
        canon.assert_consistent({"characters": 2, "relationships": 1, "canon_facts": 0})


def test_scene_and_character_prompts_say_girl_not_boy():
    aden = json.loads((ROOT / "characters" / "aden.json").read_text(encoding="utf-8"))
    scene = json.loads((ROOT / "characters" / "scenes" / "park-kite-01.json").read_text(encoding="utf-8"))
    fragment = aden["prompt_fragment"]
    assert "girl" in fragment
    assert "3-year-old boy" not in fragment
    assert "her left cheek" in fragment
    for key in ("keyframe", "image_to_video", "keyframe_baby_focus"):
        text = scene["prompts"][key]
        assert "3-year-old boy" not in text
        assert "brothers" not in text.lower()
        assert "girl" in text or "sister" in text


def test_aden_v2_single_star_clip_and_freckles_locked():
    aden = json.loads((ROOT / "characters" / "aden.json").read_text(encoding="utf-8"))
    assert aden["gender"] == "female"
    assert "TEK" in aden["hair"]["style"] or "tek" in aden["hair"]["style"]
    assert "star hair clip" in aden["prompt_fragment"]
    assert "three tiny freckles" in aden["prompt_fragment"]


def test_kaan_v2_baby_proportions_locked():
    kaan = json.loads((ROOT / "characters" / "kaan.json").read_text(encoding="utf-8"))
    assert kaan["gender"] == "male"
    assert kaan["age_years"] == 1
    assert kaan["proportions"]["heads_tall"] <= 3.0
    assert "large head" in kaan["prompt_fragment"]
    assert "short chubby legs" in kaan["prompt_fragment"]
