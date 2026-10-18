from pathlib import Path

import pytest

from ahos.character_memory import CharacterBibleStore, CharacterProfile
from ahos.localization_memory import (
    LocalizationMemoryStore,
    TerminologyViolationError,
    TranslationNotApprovedError,
    TranslationStatus,
)


def character_store(tmp_path: Path) -> CharacterBibleStore:
    store = CharacterBibleStore(tmp_path / "characters.db")
    store.upsert_profile(
        CharacterProfile(
            character_id="aden",
            display_name="Aden",
            canonical_role="lead_child",
        ),
        author="test",
        reason="seed",
    )
    return store


def test_cross_language_line_starts_translation_required(tmp_path: Path):
    store = LocalizationMemoryStore(
        tmp_path / "localization.db",
        character_store=character_store(tmp_path),
    )
    item = store.create_required(
        episode_id="S01E001",
        scene_id="SCENE-01",
        line_id="L1",
        speaker_character_id="aden",
        source_language="tr",
        target_language="de",
        source_text="Merhaba dünya",
    )

    assert item.status == TranslationStatus.TRANSLATION_REQUIRED
    assert item.localized_text == ""


def test_translation_must_be_reviewed_before_tts(tmp_path: Path):
    store = LocalizationMemoryStore(
        tmp_path / "localization.db",
        character_store=character_store(tmp_path),
    )
    first = store.create_required(
        episode_id="S01E001",
        scene_id="SCENE-01",
        line_id="L1",
        speaker_character_id="aden",
        source_language="tr",
        target_language="de",
        source_text="Merhaba",
    )
    store.submit_translation(
        first.localization_id,
        localized_text="Hallo",
        translator="translator-01",
    )

    with pytest.raises(TranslationNotApprovedError):
        store.approved_dialogue(first.localization_id)

    approved = store.approve(
        first.localization_id,
        reviewer="localization-qa-01",
    )
    assert approved.status == TranslationStatus.APPROVED
    assert store.approved_dialogue(first.localization_id).localized_text == "Hallo"


def test_locked_terminology_blocks_inconsistent_translation(tmp_path: Path):
    store = LocalizationMemoryStore(
        tmp_path / "localization.db",
        character_store=character_store(tmp_path),
    )
    store.add_terminology(
        term_id="magic-garden-de",
        source_text="Sihirli Bahçe",
        target_language="de",
        approved_text="Zaubergarten",
        locked=True,
    )
    first = store.create_required(
        episode_id="S01E001",
        scene_id="SCENE-01",
        line_id="L1",
        speaker_character_id="aden",
        source_language="tr",
        target_language="de",
        source_text="Sihirli Bahçe'ye gidelim",
    )
    store.submit_translation(
        first.localization_id,
        localized_text="Gehen wir in den magischen Garten",
        translator="translator-01",
    )

    with pytest.raises(TerminologyViolationError):
        store.approve(
            first.localization_id,
            reviewer="localization-qa-01",
        )


def test_locked_terminology_accepts_approved_recurring_term(tmp_path: Path):
    store = LocalizationMemoryStore(
        tmp_path / "localization.db",
        character_store=character_store(tmp_path),
    )
    store.add_terminology(
        term_id="magic-garden-de",
        source_text="Sihirli Bahçe",
        target_language="de",
        approved_text="Zaubergarten",
        pronunciation_hint="",
        locked=True,
    )
    first = store.create_required(
        episode_id="S01E001",
        scene_id="SCENE-01",
        line_id="L1",
        speaker_character_id="aden",
        source_language="tr",
        target_language="de",
        source_text="Sihirli Bahçe'ye gidelim",
    )
    store.submit_translation(
        first.localization_id,
        localized_text="Gehen wir zum Zaubergarten",
        translator="translator-01",
    )
    approved = store.approve(
        first.localization_id,
        reviewer="localization-qa-01",
    )

    assert approved.status == TranslationStatus.APPROVED
    assert len(store.history(first.localization_id)) == 3


def test_same_language_source_is_ready_without_fake_translation(tmp_path: Path):
    store = LocalizationMemoryStore(
        tmp_path / "localization.db",
        character_store=character_store(tmp_path),
    )
    first = store.create_required(
        episode_id="S01E001",
        scene_id="SCENE-01",
        line_id="L1",
        speaker_character_id="aden",
        source_language="tr",
        target_language="tr",
        source_text="Merhaba",
    )

    assert first.status == TranslationStatus.SOURCE_READY
    dialogue = store.approved_dialogue(first.localization_id)
    assert dialogue.localized_text == "Merhaba"
