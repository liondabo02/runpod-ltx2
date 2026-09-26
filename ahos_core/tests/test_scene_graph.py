from pathlib import Path

import pytest

from ahos.character_memory import CharacterBibleStore, CharacterProfile
from ahos.scene_graph import (
    AssetKind,
    ProductionGraphStore,
    ProductionGraphValidationError,
    SceneShotPromptAssetGraphBuilder,
    VisualStyleProfile,
)
from ahos.story_engine import (
    DeterministicLocalStoryPlanner,
    EpisodePlanningEngine,
    EpisodePlanningStore,
    EpisodeRequest,
)


def build_episode(tmp_path: Path):
    characters = CharacterBibleStore(tmp_path / "characters.db")
    for cid, name, role in (
        ("aden", "Aden", "lead_child"),
        ("kaan", "Kaan", "lead_child"),
        ("esra", "Esra", "mother"),
    ):
        characters.upsert_profile(
            CharacterProfile(
                character_id=cid,
                display_name=name,
                canonical_role=role,
                family_group="central-family",
                age_stage="young child" if role == "lead_child" else "adult",
                visual_anchors=("approved-reference",),
                continuity_rules=(f"{name} keeps established identity.",),
                locked_fields=frozenset(
                    {"display_name", "canonical_role", "family_group", "visual_anchors"}
                ),
            ),
            author="test",
            reason="seed",
        )

    episodes = EpisodePlanningStore(tmp_path / "episodes.db")
    engine = EpisodePlanningEngine(
        character_store=characters,
        episode_store=episodes,
        planner=DeterministicLocalStoryPlanner(),
    )
    version = engine.plan(
        EpisodeRequest(
            season_number=1,
            episode_number=1,
            topic="sharing",
            learning_goal="cooperate",
            cast_ids=("aden", "kaan", "esra"),
            target_duration_seconds=480,
        ),
        created_by="test",
        reason="proof",
    )
    return characters, version


def test_graph_builds_two_shots_per_scene_and_exact_duration(tmp_path: Path):
    characters, episode = build_episode(tmp_path)
    graph = SceneShotPromptAssetGraphBuilder(characters).build(episode)

    assert len(graph.scenes) == 5
    assert len(graph.shots) == 10
    assert len(graph.prompts) == 10
    assert sum(scene.duration_seconds for scene in graph.scenes) == 480

    for scene in graph.scenes:
        local = [shot for shot in graph.shots if shot.scene_id == scene.scene_id]
        assert len(local) == 2
        assert sum(shot.duration_seconds for shot in local) == scene.duration_seconds


def test_prompts_include_character_reference_assets_and_continuity(tmp_path: Path):
    characters, episode = build_episode(tmp_path)
    graph = SceneShotPromptAssetGraphBuilder(characters).build(episode)

    first = graph.prompts[0]
    assert first.character_ids == ("aden", "kaan", "esra")
    assert "Aden" in first.positive_prompt
    assert "preserve exact approved character identity" in first.positive_prompt
    assert any(asset_id.startswith("charref:aden:") for asset_id in first.reference_asset_ids)
    assert first.continuity_constraints


def test_studio_004_never_marks_outputs_as_rendered(tmp_path: Path):
    characters, episode = build_episode(tmp_path)
    graph = SceneShotPromptAssetGraphBuilder(characters).build(episode)

    outputs = [a for a in graph.assets if a.kind is AssetKind.SHOT_OUTPUT]
    assert outputs
    assert all(a.generated is False for a in outputs)
    assert all(a.source_uri.startswith("pending-render://") for a in outputs)


def test_character_asset_provenance_uses_version_hash(tmp_path: Path):
    characters, episode = build_episode(tmp_path)
    graph = SceneShotPromptAssetGraphBuilder(characters).build(episode)

    aden = next(
        a for a in graph.assets
        if a.kind is AssetKind.CHARACTER_REFERENCE
        and a.asset_id.startswith("charref:aden:")
    )
    assert aden.content_hash is not None
    assert len(aden.content_hash) == 64
    assert "character:aden" in aden.provenance


def test_graph_store_is_persistent_and_versioned(tmp_path: Path):
    characters, episode = build_episode(tmp_path)
    graph = SceneShotPromptAssetGraphBuilder(characters).build(episode)
    db = tmp_path / "graph.db"

    store = ProductionGraphStore(db)
    first = store.save(graph, created_by="test", reason="first")
    second = store.save(graph, created_by="test", reason="repeat")

    assert first.version == 1
    assert second.version == 2
    assert first.content_hash == second.content_hash
    assert store.history_count("S01E001") == 2
    assert store.current_payload("S01E001")["schema"] == "ahos.production-graph.v1"


def test_unknown_character_in_episode_fails_closed(tmp_path: Path):
    characters, episode = build_episode(tmp_path)
    # The normal Story Engine blocks this upstream; prove Scene Graph also validates.
    bad_packet = episode.packet.__class__(
        episode_id=episode.packet.episode_id,
        season_number=episode.packet.season_number,
        episode_number=episode.packet.episode_number,
        title=episode.packet.title,
        logline=episode.packet.logline,
        topic=episode.packet.topic,
        learning_goal=episode.packet.learning_goal,
        age_band=episode.packet.age_band,
        primary_language=episode.packet.primary_language,
        target_duration_seconds=episode.packet.target_duration_seconds,
        child_safe_required=episode.packet.child_safe_required,
        cast_ids=("aden", "invented"),
        continuity_notes=episode.packet.continuity_notes,
        beats=episode.packet.beats,
        scenes=episode.packet.scenes,
        owner_approved=False,
    )
    bad_episode = episode.__class__(
        episode_id=episode.episode_id,
        version=episode.version,
        content_hash=episode.content_hash,
        status=episode.status,
        created_at=episode.created_at,
        created_by=episode.created_by,
        reason=episode.reason,
        owner_decision_at=episode.owner_decision_at,
        packet=bad_packet,
    )

    with pytest.raises(ProductionGraphValidationError):
        SceneShotPromptAssetGraphBuilder(characters).build(bad_episode)


def test_visual_style_profile_is_explicit_and_renderer_ready(tmp_path: Path):
    characters, episode = build_episode(tmp_path)
    style = VisualStyleProfile(
        style_id="test-style",
        description="2D test style",
        negative_prompt="bad output",
        aspect_ratio="16:9",
        frame_rate=24,
    )
    graph = SceneShotPromptAssetGraphBuilder(characters, style=style).build(episode)

    assert graph.style.style_id == "test-style"
    assert graph.style.aspect_ratio == "16:9"
    assert all(prompt.style_id == "test-style" for prompt in graph.prompts)
