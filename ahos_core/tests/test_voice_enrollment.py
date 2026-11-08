from pathlib import Path

import pytest

from ahos.character_memory import CharacterBibleStore, CharacterProfile
from ahos.voice_continuity import VoiceContinuityStore
from ahos.voice_enrollment import (
    VoiceEnrollmentApprovalError,
    VoiceEnrollmentStore,
    VoiceReferenceRightsError,
)


SHA = "a" * 64


def stores(tmp_path: Path):
    characters = CharacterBibleStore(tmp_path / "characters.db")
    characters.upsert_profile(
        CharacterProfile(
            character_id="aden",
            display_name="Aden",
            canonical_role="lead_child",
            age_stage="young child",
        ),
        author="test",
        reason="seed",
    )
    voices = VoiceContinuityStore(
        tmp_path / "voices.db",
        character_store=characters,
    )
    enrollments = VoiceEnrollmentStore(
        tmp_path / "enrollments.db",
        character_store=characters,
        voice_store=voices,
    )
    return characters, voices, enrollments


def test_synthetic_reference_can_be_canonically_enrolled_with_owner_approval(tmp_path):
    _, voices, enrollments = stores(tmp_path)

    enrollment, binding = enrollments.enroll(
        character_id="aden",
        language="tr",
        provider_id="chatterbox-multilingual",
        voice_id="aden-tr-v1",
        speaking_style="warm, curious, age-appropriate",
        reference_audio_uri="private://voices/aden/tr/reference.wav",
        reference_sha256=SHA,
        reference_origin="synthetic",
        rights_confirmed=True,
        speaker_consent_confirmed=False,
        human_similarity_approved=True,
        owner_approved=True,
    )

    assert enrollment.version == 1
    assert binding.voice_id == "aden-tr-v1"
    assert voices.require("aden", "tr").reference_audio_uri.endswith("reference.wav")


def test_recorded_human_reference_requires_speaker_consent(tmp_path):
    _, _, enrollments = stores(tmp_path)

    with pytest.raises(VoiceReferenceRightsError):
        enrollments.enroll(
            character_id="aden",
            language="tr",
            provider_id="chatterbox-multilingual",
            voice_id="aden-tr-v1",
            speaking_style="warm",
            reference_audio_uri="private://voices/aden/tr/reference.wav",
            reference_sha256=SHA,
            reference_origin="recorded-human",
            rights_confirmed=True,
            speaker_consent_confirmed=False,
            human_similarity_approved=True,
            owner_approved=True,
        )


def test_human_similarity_approval_is_required(tmp_path):
    _, _, enrollments = stores(tmp_path)

    with pytest.raises(VoiceEnrollmentApprovalError):
        enrollments.enroll(
            character_id="aden",
            language="tr",
            provider_id="chatterbox-multilingual",
            voice_id="aden-tr-v1",
            speaking_style="warm",
            reference_audio_uri="private://voices/aden/tr/reference.wav",
            reference_sha256=SHA,
            reference_origin="synthetic",
            rights_confirmed=True,
            speaker_consent_confirmed=False,
            human_similarity_approved=False,
            owner_approved=True,
        )


def test_owner_approval_is_required(tmp_path):
    _, _, enrollments = stores(tmp_path)

    with pytest.raises(VoiceEnrollmentApprovalError):
        enrollments.enroll(
            character_id="aden",
            language="tr",
            provider_id="chatterbox-multilingual",
            voice_id="aden-tr-v1",
            speaking_style="warm",
            reference_audio_uri="private://voices/aden/tr/reference.wav",
            reference_sha256=SHA,
            reference_origin="synthetic",
            rights_confirmed=True,
            speaker_consent_confirmed=False,
            human_similarity_approved=True,
            owner_approved=False,
        )


def test_reenrollment_versions_and_overrides_voice_binding(tmp_path):
    _, voices, enrollments = stores(tmp_path)

    first, _ = enrollments.enroll(
        character_id="aden",
        language="tr",
        provider_id="chatterbox-multilingual",
        voice_id="aden-tr-v1",
        speaking_style="warm",
        reference_audio_uri="private://voices/aden/tr/reference-v1.wav",
        reference_sha256="a" * 64,
        reference_origin="synthetic",
        rights_confirmed=True,
        speaker_consent_confirmed=False,
        human_similarity_approved=True,
        owner_approved=True,
    )
    second, binding = enrollments.enroll(
        character_id="aden",
        language="tr",
        provider_id="chatterbox-multilingual",
        voice_id="aden-tr-v2",
        speaking_style="warm, playful",
        reference_audio_uri="private://voices/aden/tr/reference-v2.wav",
        reference_sha256="b" * 64,
        reference_origin="synthetic",
        rights_confirmed=True,
        speaker_consent_confirmed=False,
        human_similarity_approved=True,
        owner_approved=True,
    )

    assert first.version == 1
    assert second.version == 2
    assert binding.version == 2
    assert voices.require("aden", "tr").voice_id == "aden-tr-v2"
    assert len(enrollments.history("aden", "tr")) == 2
