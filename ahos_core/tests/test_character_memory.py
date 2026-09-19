from dataclasses import replace
from pathlib import Path

import pytest

from ahos.character_memory import (
    CharacterBibleStore,
    CharacterProfile,
    CharacterRelationship,
    ContinuityReferenceError,
    LockedCharacterFieldError,
)


def profile(character_id="aden", display_name="Aden"):
    return CharacterProfile(
        character_id=character_id,
        display_name=display_name,
        canonical_role="lead_child",
        family_group="central-family",
        age_stage="young child",
        visual_anchors=("brown hair",),
        personality_anchors=("curious",),
        locked_fields=frozenset(
            {
                "display_name",
                "canonical_role",
                "family_group",
                "visual_anchors",
            }
        ),
    )


def test_profile_persists_across_reopen(tmp_path: Path):
    db = tmp_path / "characters.db"
    store = CharacterBibleStore(db)
    store.upsert_profile(profile(), author="test", reason="seed")

    reopened = CharacterBibleStore(db)
    loaded = reopened.get_profile("aden")

    assert loaded is not None
    assert loaded.display_name == "Aden"
    assert reopened.version_history("aden")[0].version == 1


def test_version_history_increments_for_allowed_change(tmp_path: Path):
    store = CharacterBibleStore(tmp_path / "characters.db")
    first = profile()
    store.upsert_profile(first, author="test", reason="seed")

    second = replace(
        first,
        personality_anchors=("curious", "patient"),
    )
    store.upsert_profile(
        second,
        author="continuity-editor",
        reason="character development",
    )

    history = store.version_history("aden")
    assert [item.version for item in history] == [1, 2]
    assert history[-1].profile.personality_anchors == ("curious", "patient")


def test_locked_character_field_requires_owner_override(tmp_path: Path):
    store = CharacterBibleStore(tmp_path / "characters.db")
    first = profile()
    store.upsert_profile(first, author="test", reason="seed")

    changed = replace(first, display_name="Different")
    with pytest.raises(LockedCharacterFieldError):
        store.upsert_profile(
            changed,
            author="studio-writer",
            reason="unauthorized rename",
        )


def test_owner_override_is_versioned_and_auditable(tmp_path: Path):
    store = CharacterBibleStore(tmp_path / "characters.db")
    first = profile()
    store.upsert_profile(first, author="test", reason="seed")

    changed = replace(first, display_name="Aden Updated")
    version = store.upsert_profile(
        changed,
        author="owner",
        reason="explicit canon correction",
        owner_override=True,
    )

    assert version.version == 2
    assert version.owner_override is True
    assert store.get_profile("aden").display_name == "Aden Updated"


def test_relationships_require_known_characters(tmp_path: Path):
    store = CharacterBibleStore(tmp_path / "characters.db")
    store.upsert_profile(profile(), author="test", reason="seed")

    with pytest.raises(ContinuityReferenceError):
        store.add_relationship(
            CharacterRelationship(
                relationship_id="aden-sibling-kaan",
                from_character_id="aden",
                to_character_id="kaan",
                relationship_type="sibling_of",
            )
        )


def test_locked_canon_fact_cannot_silently_change(tmp_path: Path):
    store = CharacterBibleStore(tmp_path / "characters.db")
    store.add_canon_fact(
        fact_id="series-format",
        scope_type="series",
        scope_id="main",
        fact_key="format",
        fact_value="episodic",
        locked=True,
    )

    with pytest.raises(LockedCharacterFieldError):
        store.add_canon_fact(
            fact_id="series-format",
            scope_type="series",
            scope_id="main",
            fact_key="format",
            fact_value="anthology",
            locked=True,
        )


def test_episode_continuity_survives_reopen(tmp_path: Path):
    db = tmp_path / "characters.db"
    store = CharacterBibleStore(db)
    store.record_episode_event(
        event_id="ep001-001",
        episode_id="EP001",
        sequence_no=1,
        event_type="lesson_learned",
        payload={"character_id": "aden", "lesson": "sharing"},
    )

    reopened = CharacterBibleStore(db)
    events = reopened.episode_events("EP001")

    assert len(events) == 1
    assert events[0].payload["lesson"] == "sharing"


def test_snapshot_contains_hashes_and_memory_layers(tmp_path: Path):
    store = CharacterBibleStore(tmp_path / "characters.db")
    store.upsert_profile(profile(), author="test", reason="seed")
    snap = store.snapshot()

    assert snap["schema"] == "ahos.character-bible.v1"
    assert len(snap["characters"]) == 1
    assert len(snap["characters"][0]["content_hash"]) == 64
    assert "relationships" in snap
    assert "canon_facts" in snap
    assert "episode_events" in snap
