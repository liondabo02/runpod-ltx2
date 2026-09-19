import json
from pathlib import Path

import pytest

from ahos.character_memory import CharacterBibleStore, CharacterProfile
from ahos.episode_casting import EpisodeGuestCastDirector, StructuredGuestCastPlanner
from ahos.episode_voice_orchestrator import (
    EpisodeVoiceReadinessError,
    VoiceReadyEpisodeOrchestrator,
)
from ahos.story_engine import (
    DialogueLine,
    EpisodeProductionPacket,
    EpisodeRequest,
    SceneDraft,
    StoryBeat,
)


def character_store(tmp_path: Path):
    store = CharacterBibleStore(tmp_path / "characters.db")
    for cid, stage in (("aden", "preschool"), ("kaan", "toddler")):
        store.upsert_profile(
            CharacterProfile(
                character_id=cid,
                display_name=cid.title(),
                canonical_role="lead_child",
                age_stage=stage,
            ),
            author="test",
            reason="seed",
        )
    return store


def request():
    return EpisodeRequest(
        season_number=1,
        episode_number=12,
        topic="meeting a police officer and visiting a care home",
        learning_goal="learn about helpers and listening to older people",
        cast_ids=("aden", "kaan"),
        target_duration_seconds=480,
        primary_language="tr",
    )


def guest_generator(_: str) -> str:
    return json.dumps(
        {
            "guest_characters": [
                {
                    "guest_key": "police",
                    "display_name": "Polis Elif",
                    "role": "police officer",
                    "species": "human",
                    "age_years": 33,
                    "age_stage": "adult",
                    "gender_presentation": "woman",
                    "speaking": True,
                },
                {
                    "guest_key": "elder",
                    "display_name": "Nermin Teyze",
                    "role": "care-home resident",
                    "species": "human",
                    "age_years": 79,
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


def ready(tmp_path: Path):
    store = character_store(tmp_path)
    orchestrator = VoiceReadyEpisodeOrchestrator(
        guest_planner=StructuredGuestCastPlanner(guest_generator),
        guest_director=EpisodeGuestCastDirector(store),
    )
    return orchestrator, orchestrator.prepare(request())


def packet_for(ready_plan):
    ids = ready_plan.preparation.expanded_request.cast_ids
    police = ready_plan.preparation.guest_character_ids[0]
    elder = ready_plan.preparation.guest_character_ids[1]
    cat = ready_plan.preparation.guest_character_ids[2]
    return EpisodeProductionPacket(
        episode_id="S01E012",
        season_number=1,
        episode_number=12,
        title="Helpers",
        logline="Aden and Kaan meet community helpers.",
        topic="helpers",
        learning_goal="kindness",
        age_band="young children",
        primary_language="tr",
        target_duration_seconds=480,
        child_safe_required=True,
        cast_ids=ids,
        continuity_notes=(),
        beats=(
            StoryBeat("B1", "setup", "setup", "", ""),
            StoryBeat("B2", "middle", "middle", "", ""),
            StoryBeat("B3", "end", "end", "", ""),
        ),
        scenes=(
            SceneDraft(
                scene_id="S1",
                title="Police",
                setting="park",
                cast_ids=("aden", police),
                duration_seconds=160,
                objective="meet helper",
                action_summary="talk",
                dialogue=(
                    DialogueLine("aden", "Merhaba"),
                    DialogueLine(police, "Merhaba çocuklar"),
                ),
            ),
            SceneDraft(
                scene_id="S2",
                title="Care home",
                setting="care home",
                cast_ids=("kaan", elder),
                duration_seconds=160,
                objective="listen",
                action_summary="talk",
                dialogue=(
                    DialogueLine(kaan, "Merhaba"),
                    DialogueLine(elder, "Hoş geldiniz"),
                ),
            ),
            SceneDraft(
                scene_id="S3",
                title="Cat",
                setting="garden",
                cast_ids=("aden", cat),
                duration_seconds=160,
                objective="pet animal",
                action_summary="cat meows",
                dialogue=(DialogueLine("aden", "Misket ne tatlı"),),
            ),
        ),
        owner_approved=False,
    )


def test_prompt_to_cast_preparation_covers_recurring_guests_and_pet(tmp_path: Path):
    orchestrator, ready_plan = ready(tmp_path)
    modes = orchestrator.audio_modes(ready_plan)

    assert modes["aden"] == "speech"
    assert modes["kaan"] == "early_speech"
    assert len(ready_plan.preparation.guest_character_ids) == 3
    pet_id = ready_plan.preparation.guest_character_ids[2]
    assert modes[pet_id] == "animal_vocalization"


def test_final_screenplay_is_voice_ready_when_every_character_is_prepared(tmp_path: Path):
    orchestrator, ready_plan = ready(tmp_path)
    orchestrator.verify_final_packet(packet_for(ready_plan), ready_plan)


def test_non_talking_pet_cannot_receive_sentence_dialogue(tmp_path: Path):
    orchestrator, ready_plan = ready(tmp_path)
    packet = packet_for(ready_plan)
    cat = ready_plan.preparation.guest_character_ids[2]

    bad_scene = SceneDraft(
        scene_id="S3",
        title="Cat",
        setting="garden",
        cast_ids=("aden", cat),
        duration_seconds=160,
        objective="pet animal",
        action_summary="cat talks",
        dialogue=(
            DialogueLine(cat, "Ben konuşan bir kediyim"),
        ),
    )
    bad = EpisodeProductionPacket(
        episode_id=packet.episode_id,
        season_number=packet.season_number,
        episode_number=packet.episode_number,
        title=packet.title,
        logline=packet.logline,
        topic=packet.topic,
        learning_goal=packet.learning_goal,
        age_band=packet.age_band,
        primary_language=packet.primary_language,
        target_duration_seconds=packet.target_duration_seconds,
        child_safe_required=packet.child_safe_required,
        cast_ids=packet.cast_ids,
        continuity_notes=packet.continuity_notes,
        beats=packet.beats,
        scenes=(packet.scenes[0], packet.scenes[1], bad_scene),
        owner_approved=False,
    )

    with pytest.raises(EpisodeVoiceReadinessError):
        orchestrator.verify_final_packet(bad, ready_plan)
