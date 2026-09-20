from pathlib import Path

import pytest

from ahos.audio_pipeline import (
    LocalizedDialogue,
    UnsupportedLanguageError,
)
from ahos.character_memory import CharacterBibleStore, CharacterProfile
from ahos.voice_continuity import (
    LockedVoiceBindingError,
    VoiceBindingMissingError,
    VoiceContinuityStore,
)


def character_store(tmp_path: Path) -> CharacterBibleStore:
    store = CharacterBibleStore(tmp_path / "characters.db")
    store.upsert_profile(
        CharacterProfile(
            character_id="aden",
            display_name="Aden",
            canonical_role="lead_child",
            family_group="central-family",
            age_stage="young child",
        ),
        author="test",
        reason="seed",
    )
    return store


def test_voice_binding_persists_and_resolves_exact_language(tmp_path: Path):
    chars = character_store(tmp_path)
    db = tmp_path / "voices.db"
    voices = VoiceContinuityStore(db, character_store=chars)
    voices.bind(
        character_id="aden",
        language="tr",
        provider_id="chatterbox-multilingual",
        voice_id="aden-tr-v1",
        reference_audio_uri="private://voices/aden/reference.wav",
    )

    reopened = VoiceContinuityStore(db, character_store=chars)
    binding = reopened.require("aden", "tr")

    assert binding.provider_id == "chatterbox-multilingual"
    assert binding.voice_id == "aden-tr-v1"
    assert binding.version == 1


def test_voice_change_requires_owner_override(tmp_path: Path):
    chars = character_store(tmp_path)
    voices = VoiceContinuityStore(tmp_path / "voices.db", character_store=chars)
    voices.bind(
        character_id="aden",
        language="en",
        provider_id="runpod-kokoro",
        voice_id="af_heart",
    )

    with pytest.raises(LockedVoiceBindingError):
        voices.bind(
            character_id="aden",
            language="en",
            provider_id="runpod-kokoro",
            voice_id="am_adam",
        )

    changed = voices.bind(
        character_id="aden",
        language="en",
        provider_id="runpod-kokoro",
        voice_id="am_adam",
        owner_override=True,
    )
    assert changed.version == 2
    assert changed.owner_override is True


def test_wrong_language_provider_is_rejected(tmp_path: Path):
    chars = character_store(tmp_path)
    voices = VoiceContinuityStore(tmp_path / "voices.db", character_store=chars)

    with pytest.raises(UnsupportedLanguageError):
        voices.bind(
            character_id="aden",
            language="tr",
            provider_id="runpod-kokoro",
            voice_id="af_heart",
        )


def test_missing_language_never_falls_back(tmp_path: Path):
    chars = character_store(tmp_path)
    voices = VoiceContinuityStore(tmp_path / "voices.db", character_store=chars)
    voices.bind(
        character_id="aden",
        language="en",
        provider_id="runpod-kokoro",
        voice_id="af_heart",
    )

    with pytest.raises(VoiceBindingMissingError):
        voices.voice_profile("aden", "de")


def test_voice_binding_drives_audio_provider_selection(tmp_path: Path):
    chars = character_store(tmp_path)
    voices = VoiceContinuityStore(tmp_path / "voices.db", character_store=chars)
    voices.bind(
        character_id="aden",
        language="tr",
        provider_id="chatterbox-multilingual",
        voice_id="aden-tr-v1",
        reference_audio_uri="private://voices/aden/reference.wav",
    )
    dialogue = LocalizedDialogue(
        line_id="L1",
        episode_id="S01E001",
        scene_id="SCENE-01",
        speaker_character_id="aden",
        source_language="tr",
        target_language="tr",
        source_text="Merhaba",
        localized_text="Merhaba",
        localization_status="source_ready",
    )

    job = voices.make_tts_job(
        dialogue,
        allow_paid=True,
        allow_external=True,
    )

    assert job.provider_id == "chatterbox-multilingual"
    assert job.payload["voice_id"] == "aden-tr-v1"
    assert job.payload["reference_audio_uri"] == (
        "private://voices/aden/reference.wav"
    )
