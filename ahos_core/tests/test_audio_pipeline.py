from pathlib import Path

import pytest

from ahos.audio_pipeline import (
    AudioPipelineError,
    AudioProductionPlanner,
    AudioProviderDescriptor,
    AudioProviderRegistry,
    UnsupportedLanguageError,
    VoiceProfile,
    AudioManifestStore,
    DEFAULT_LANGUAGE_POLICIES,
    default_audio_provider_registry,
)
from ahos.character_memory import CharacterBibleStore, CharacterProfile


def store(tmp_path: Path):
    db = CharacterBibleStore(tmp_path / "characters.db")
    db.upsert_profile(
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
    return db


def test_translation_stub_never_fakes_translation(tmp_path: Path):
    planner = AudioProductionPlanner(character_store=store(tmp_path))
    line = planner.make_localization_stub(
        line_id="L1",
        episode_id="S01E001",
        scene_id="SCENE-01",
        speaker_character_id="aden",
        source_language="tr",
        target_language="de",
        source_text="Merhaba",
    )
    assert line.localized_text == ""
    assert line.localization_status == "translation_required"


def test_source_language_can_be_tts_ready(tmp_path: Path):
    planner = AudioProductionPlanner(character_store=store(tmp_path))
    line = planner.make_localization_stub(
        line_id="L1",
        episode_id="S01E001",
        scene_id="SCENE-01",
        speaker_character_id="aden",
        source_language="en",
        target_language="en",
        source_text="Hello",
    )
    voice = VoiceProfile(
        character_id="aden",
        voice_id="aden-v1",
        provider_preference=("runpod-kokoro",),
    )
    job = planner.make_tts_job(
        line,
        voice=voice,
        allow_paid=True,
        allow_external=True,
    )
    assert job.provider_id == "runpod-kokoro"
    assert job.paid is True


def test_multilingual_commercial_selection_prefers_chatterbox(tmp_path: Path):
    planner = AudioProductionPlanner(character_store=store(tmp_path))
    line = planner.make_localization_stub(
        line_id="L1",
        episode_id="S01E001",
        scene_id="SCENE-01",
        speaker_character_id="aden",
        source_language="tr",
        target_language="tr",
        source_text="Merhaba",
    )
    voice = VoiceProfile(
        character_id="aden",
        voice_id="aden-v1",
        provider_preference=("chatterbox-multilingual",),
    )
    job = planner.make_tts_job(
        line,
        voice=voice,
        allow_paid=True,
        allow_external=True,
        commercial_use=True,
    )
    assert job.provider_id == "chatterbox-multilingual"


def test_kurmanji_is_required_but_unverified_tts_fails_closed():
    required = tuple(policy.code for policy in DEFAULT_LANGUAGE_POLICIES if policy.required)
    assert required == ("tr", "ku-latn", "de", "ar", "fr", "es", "en")

    with pytest.raises(UnsupportedLanguageError):
        default_audio_provider_registry().choose(
            language="ku-latn",
            capability="tts",
            allow_paid=True,
            allow_external=True,
            commercial_use=True,
        )


def test_translation_required_blocks_tts(tmp_path: Path):
    planner = AudioProductionPlanner(character_store=store(tmp_path))
    line = planner.make_localization_stub(
        line_id="L1",
        episode_id="S01E001",
        scene_id="SCENE-01",
        speaker_character_id="aden",
        source_language="tr",
        target_language="de",
        source_text="Merhaba",
    )
    with pytest.raises(AudioPipelineError):
        planner.make_tts_job(
            line,
            voice=VoiceProfile("aden", "aden-v1", ("chatterbox-multilingual",)),
            allow_paid=True,
            allow_external=True,
        )


def test_commercial_policy_blocks_research_only_provider():
    registry = AudioProviderRegistry(
        (
            AudioProviderDescriptor(
                provider_id="research-only",
                name="Research",
                supported_languages=frozenset({"en"}),
                capabilities=frozenset({"tts"}),
                paid=False,
                external=False,
                commercial_default=False,
                priority=1,
            ),
        )
    )
    with pytest.raises(UnsupportedLanguageError):
        registry.choose(
            language="en",
            capability="tts",
            allow_paid=True,
            allow_external=True,
            commercial_use=True,
        )


def test_audio_manifest_is_persistent(tmp_path: Path):
    planner = AudioProductionPlanner(character_store=store(tmp_path))
    line = planner.make_localization_stub(
        line_id="L1",
        episode_id="S01E001",
        scene_id="SCENE-01",
        speaker_character_id="aden",
        source_language="en",
        target_language="en",
        source_text="Hello",
    )
    job = planner.make_tts_job(
        line,
        voice=VoiceProfile("aden", "aden-v1", ("runpod-kokoro",)),
        allow_paid=True,
        allow_external=True,
    )
    db = tmp_path / "audio.db"
    AudioManifestStore(db).upsert_planned(job)
    assert AudioManifestStore(db).count("S01E001") == 1
