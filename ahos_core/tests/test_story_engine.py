import json
from pathlib import Path

import pytest

from ahos.character_memory import (
    CharacterBibleStore,
    CharacterProfile,
    CharacterRelationship,
)
from ahos.story_engine import (
    DeterministicLocalStoryPlanner,
    EpisodePlanningEngine,
    EpisodePlanningStore,
    EpisodeRequest,
    EpisodeStatus,
    InvalidStoryPlanError,
    StructuredJsonStoryPlanner,
    UnknownStoryCharacterError,
)


def build_character_store(path: Path):
    store = CharacterBibleStore(path)
    for character_id, name, role in (
        ("aden", "Aden", "lead_child"),
        ("kaan", "Kaan", "lead_child"),
        ("esra", "Esra", "mother"),
    ):
        store.upsert_profile(
            CharacterProfile(
                character_id=character_id,
                display_name=name,
                canonical_role=role,
                family_group="central-family",
                age_stage="young child" if role == "lead_child" else "adult",
                personality_anchors=("kind",),
                continuity_rules=(f"{name} keeps established family relationships.",),
            ),
            author="test",
            reason="seed",
        )
    store.add_relationship(
        CharacterRelationship(
            relationship_id="aden-sibling-kaan",
            from_character_id="aden",
            to_character_id="kaan",
            relationship_type="sibling_of",
        )
    )
    return store


def request():
    return EpisodeRequest(
        season_number=1,
        episode_number=1,
        topic="sharing",
        learning_goal="learn to share and cooperate",
        cast_ids=("aden", "kaan", "esra"),
        target_duration_seconds=480,
        primary_language="tr",
    )


def test_deterministic_story_plan_is_season_aware_and_duration_exact(tmp_path: Path):
    characters = build_character_store(tmp_path / "characters.db")
    episodes = EpisodePlanningStore(tmp_path / "episodes.db")
    engine = EpisodePlanningEngine(
        character_store=characters,
        episode_store=episodes,
        planner=DeterministicLocalStoryPlanner(),
    )

    version = engine.plan(
        request(),
        created_by="studio-story-director-01",
        reason="offline proof",
    )

    assert version.episode_id == "S01E001"
    assert version.status is EpisodeStatus.READY_FOR_OWNER_REVIEW
    assert version.packet.owner_approved is False
    assert sum(s.duration_seconds for s in version.packet.scenes) == 480
    assert len(version.packet.scenes) == 5


def test_unknown_character_is_rejected_before_planning(tmp_path: Path):
    characters = build_character_store(tmp_path / "characters.db")
    engine = EpisodePlanningEngine(
        character_store=characters,
        episode_store=EpisodePlanningStore(tmp_path / "episodes.db"),
        planner=DeterministicLocalStoryPlanner(),
    )

    bad = EpisodeRequest(
        season_number=1,
        episode_number=2,
        topic="friendship",
        learning_goal="be kind",
        cast_ids=("aden", "invented-person"),
    )

    with pytest.raises(UnknownStoryCharacterError):
        engine.plan(bad, created_by="test", reason="bad cast")


def test_episode_owner_approval_is_explicit_and_audited(tmp_path: Path):
    characters = build_character_store(tmp_path / "characters.db")
    episodes = EpisodePlanningStore(tmp_path / "episodes.db")
    engine = EpisodePlanningEngine(
        character_store=characters,
        episode_store=episodes,
        planner=DeterministicLocalStoryPlanner(),
    )
    version = engine.plan(
        request(),
        created_by="studio-story-director-01",
        reason="draft",
    )
    assert version.status is EpisodeStatus.READY_FOR_OWNER_REVIEW

    approved = episodes.decide("S01E001", approved=True)
    assert approved.status is EpisodeStatus.APPROVED
    assert approved.packet.owner_approved is True
    assert approved.owner_decision_at is not None


def test_structured_planner_cannot_invent_dialogue_speaker(tmp_path: Path):
    characters = build_character_store(tmp_path / "characters.db")

    def fake_generator(prompt: str) -> str:
        return json.dumps(
            {
                "title": "Test",
                "logline": "Test logline",
                "continuity_notes": [],
                "beats": [
                    {"beat_id": "B1", "purpose": "setup", "summary": "a", "emotional_value": "a", "learning_value": "a"},
                    {"beat_id": "B2", "purpose": "challenge", "summary": "b", "emotional_value": "b", "learning_value": "b"},
                    {"beat_id": "B3", "purpose": "resolution", "summary": "c", "emotional_value": "c", "learning_value": "c"},
                ],
                "scenes": [
                    {
                        "scene_id": "S1",
                        "title": "One",
                        "setting": "home",
                        "cast_ids": ["aden", "kaan", "esra"],
                        "duration_seconds": 160,
                        "objective": "setup",
                        "action_summary": "x",
                        "dialogue": [{"speaker_character_id": "aden", "text": "x"}],
                    },
                    {
                        "scene_id": "S2",
                        "title": "Two",
                        "setting": "home",
                        "cast_ids": ["aden", "kaan", "esra"],
                        "duration_seconds": 160,
                        "objective": "challenge",
                        "action_summary": "y",
                        "dialogue": [{"speaker_character_id": "invented", "text": "y"}],
                    },
                    {
                        "scene_id": "S3",
                        "title": "Three",
                        "setting": "home",
                        "cast_ids": ["aden", "kaan", "esra"],
                        "duration_seconds": 160,
                        "objective": "resolve",
                        "action_summary": "z",
                        "dialogue": [{"speaker_character_id": "kaan", "text": "z"}],
                    },
                ],
            }
        )

    engine = EpisodePlanningEngine(
        character_store=characters,
        episode_store=EpisodePlanningStore(tmp_path / "episodes.db"),
        planner=StructuredJsonStoryPlanner(fake_generator),
    )

    with pytest.raises(InvalidStoryPlanError):
        engine.plan(request(), created_by="test", reason="invalid AI output")


def test_persistent_episode_history_survives_reopen(tmp_path: Path):
    characters = build_character_store(tmp_path / "characters.db")
    episode_db = tmp_path / "episodes.db"
    engine = EpisodePlanningEngine(
        character_store=characters,
        episode_store=EpisodePlanningStore(episode_db),
        planner=DeterministicLocalStoryPlanner(),
    )
    engine.plan(request(), created_by="test", reason="first")

    reopened = EpisodePlanningStore(episode_db)
    current = reopened.get_current("S01E001")
    assert current is not None
    assert current.version == 1
    assert current.packet.title


def test_structured_planner_prompt_contains_only_allowed_cast(tmp_path: Path):
    characters = build_character_store(tmp_path / "characters.db")
    captured = {}

    def fake_generator(prompt: str) -> str:
        captured["prompt"] = prompt
        return json.dumps(
            {
                "title": "Safe plan",
                "logline": "Safe logline",
                "continuity_notes": ["keep established relationships"],
                "beats": [
                    {"beat_id": "B1", "purpose": "setup", "summary": "a", "emotional_value": "a", "learning_value": "a"},
                    {"beat_id": "B2", "purpose": "middle", "summary": "b", "emotional_value": "b", "learning_value": "b"},
                    {"beat_id": "B3", "purpose": "end", "summary": "c", "emotional_value": "c", "learning_value": "c"},
                ],
                "scenes": [
                    {
                        "scene_id": "S1",
                        "title": "One",
                        "setting": "home",
                        "cast_ids": ["aden", "kaan", "esra"],
                        "duration_seconds": 160,
                        "objective": "setup",
                        "action_summary": "a",
                        "dialogue": [{"speaker_character_id": "aden", "text": "a"}],
                    },
                    {
                        "scene_id": "S2",
                        "title": "Two",
                        "setting": "home",
                        "cast_ids": ["aden", "kaan", "esra"],
                        "duration_seconds": 160,
                        "objective": "middle",
                        "action_summary": "b",
                        "dialogue": [{"speaker_character_id": "kaan", "text": "b"}],
                    },
                    {
                        "scene_id": "S3",
                        "title": "Three",
                        "setting": "home",
                        "cast_ids": ["aden", "kaan", "esra"],
                        "duration_seconds": 160,
                        "objective": "end",
                        "action_summary": "c",
                        "dialogue": [{"speaker_character_id": "esra", "text": "c"}],
                    },
                ],
            }
        )

    engine = EpisodePlanningEngine(
        character_store=characters,
        episode_store=EpisodePlanningStore(tmp_path / "episodes.db"),
        planner=StructuredJsonStoryPlanner(fake_generator),
    )
    engine.plan(request(), created_by="test", reason="structured")

    prompt = captured["prompt"]
    assert "aden" in prompt
    assert "kaan" in prompt
    assert "esra" in prompt
    assert "Do not add owner approval" in prompt
