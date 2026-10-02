import json
from pathlib import Path

import pytest

from ahos.character_memory import CharacterBibleStore, CharacterProfile
from ahos.episode_casting import (
    EpisodeGuestCastDirector,
    GuestCharacterBrief,
    InvalidGuestCharacterError,
    StructuredGuestCastPlanner,
    build_voice_design_brief,
    core_cast_voice_briefs,
)
from ahos.story_engine import EpisodeRequest


def base_store(tmp_path: Path):
    store = CharacterBibleStore(tmp_path / "characters.db")
    for cid in ("aden", "kaan"):
        store.upsert_profile(
            CharacterProfile(
                character_id=cid,
                display_name=cid.title(),
                canonical_role="lead_child",
                age_stage="preschool" if cid == "aden" else "toddler",
            ),
            author="test",
            reason="seed",
        )
    return store


def request():
    return EpisodeRequest(
        season_number=1,
        episode_number=7,
        topic="visiting a care home",
        learning_goal="show kindness and listen to older people",
        cast_ids=("aden", "kaan"),
        target_duration_seconds=480,
        primary_language="tr",
    )


def test_core_cast_age_rules_keep_aden_child_and_babies_nonverbal():
    briefs = {item.character_id: item for item in core_cast_voice_briefs()}
    assert briefs["aden"].speech_mode == "speech"
    assert "preschool-age" in briefs["aden"].design_instruction
    assert "Never sound like an adult" in briefs["aden"].design_instruction
    assert briefs["medine"].speech_mode == "infant_vocalization"
    assert briefs["medine"].requires_tts is False
    assert briefs["ramin"].requires_sfx is True


def test_police_guest_voice_uses_scenario_age_and_gender(tmp_path: Path):
    director = EpisodeGuestCastDirector(base_store(tmp_path))
    prepared = director.prepare(
        request(),
        (
            GuestCharacterBrief(
                guest_key="police-officer",
                display_name="Polis Elif",
                role="police officer",
                species="human",
                age_years=32,
                age_stage="adult",
                gender_presentation="woman",
                speaking=True,
                personality_hint="calm, reassuring, professional",
            ),
        ),
    )

    brief = prepared.voice_briefs[0]
    assert brief.speech_mode == "speech"
    assert "adult woman" in brief.design_instruction
    assert "police officer" in brief.design_instruction
    assert prepared.guest_character_ids[0] in prepared.expanded_request.cast_ids


def test_elder_guest_is_respectful_not_caricatured(tmp_path: Path):
    director = EpisodeGuestCastDirector(base_store(tmp_path))
    prepared = director.prepare(
        request(),
        (
            GuestCharacterBrief(
                guest_key="care-home-resident",
                display_name="Nermin Teyze",
                role="care-home resident",
                species="human",
                age_years=78,
                age_stage="elderly",
                gender_presentation="woman",
                speaking=True,
            ),
        ),
    )
    instruction = prepared.voice_briefs[0].design_instruction
    assert "older woman adult" in instruction
    assert "never caricature age" in instruction


def test_non_talking_pet_routes_to_animal_vocalization():
    brief = build_voice_design_brief(
        character_id="guest:S01E001:cat-01",
        display_name="Misket",
        role="pet cat",
        species="cat",
        age_years=3,
        age_stage="adult",
        gender_presentation="unspecified",
        speaking=False,
        talking_animal=False,
        persistent_scope="episode:S01E001",
    )
    assert brief.speech_mode == "animal_vocalization"
    assert brief.requires_tts is False
    assert brief.requires_sfx is True


def test_talking_animal_gets_voice_design_plus_species_sfx():
    brief = build_voice_design_brief(
        character_id="guest:S01E001:dog-01",
        display_name="Boncuk",
        role="talking pet dog",
        species="dog",
        age_years=4,
        age_stage="adult",
        gender_presentation="boy",
        speaking=True,
        talking_animal=True,
        persistent_scope="episode:S01E001",
    )
    assert brief.speech_mode == "talking_animal"
    assert brief.requires_tts is True
    assert brief.requires_sfx is True


def test_speaking_human_guest_requires_explicit_gender_metadata(tmp_path: Path):
    director = EpisodeGuestCastDirector(base_store(tmp_path))
    with pytest.raises(InvalidGuestCharacterError):
        director.prepare(
            request(),
            (
                GuestCharacterBrief(
                    guest_key="doctor",
                    display_name="Doktor",
                    role="doctor",
                    age_years=40,
                    gender_presentation="unspecified",
                ),
            ),
        )


def test_guest_planner_contract_can_return_police_elder_and_pet():
    def fake_generator(prompt: str) -> str:
        assert "ahos.guest-cast.v1" in prompt
        return json.dumps(
            {
                "guest_characters": [
                    {
                        "guest_key": "police",
                        "display_name": "Polis Elif",
                        "role": "police officer",
                        "age_years": 32,
                        "age_stage": "adult",
                        "gender_presentation": "woman",
                        "speaking": True,
                    },
                    {
                        "guest_key": "elder",
                        "display_name": "Nermin Teyze",
                        "role": "care-home resident",
                        "age_years": 78,
                        "age_stage": "elderly",
                        "gender_presentation": "woman",
                        "speaking": True,
                    },
                    {
                        "guest_key": "cat",
                        "display_name": "Misket",
                        "role": "pet cat",
                        "species": "cat",
                        "age_stage": "adult",
                        "gender_presentation": "unspecified",
                        "speaking": False,
                        "talking_animal": False,
                    },
                ]
            }
        )

    planned = StructuredGuestCastPlanner(fake_generator).plan(request())
    assert len(planned) == 3
    assert planned[0].role == "police officer"
    assert planned[1].age_years == 78
    assert planned[2].species == "cat"

def test_recurring_adult_voice_metadata_uses_exact_owner_ages():
    from ahos.core_cast_voice_catalog import CORE_CAST_VOICE_SPECS

    specs = {item.character_id: item for item in CORE_CAST_VOICE_SPECS}
    expected = {
        "harun": (30.0, "man"),
        "davut": (30.0, "man"),
        "ahmet": (33.0, "man"),
        "esma": (29.0, "woman"),
        "fatos": (30.0, "woman"),
        "esra": (33.0, "woman"),
        "veysel": (33.0, "man"),
        "oznur": (31.0, "woman"),
    }

    for character_id, (age_years, gender) in expected.items():
        assert specs[character_id].age_years == age_years
        assert specs[character_id].gender_presentation == gender


def test_core_voice_briefs_include_exact_adult_age_and_distinct_direction():
    briefs = {item.character_id: item for item in core_cast_voice_briefs()}

    assert "30" in briefs["harun"].design_instruction
    assert "33" in briefs["ahmet"].design_instruction
    assert "29" in briefs["esma"].design_instruction
    assert "31" in briefs["oznur"].design_instruction
    assert briefs["harun"].design_instruction != briefs["davut"].design_instruction
    assert briefs["esra"].design_instruction != briefs["fatos"].design_instruction
