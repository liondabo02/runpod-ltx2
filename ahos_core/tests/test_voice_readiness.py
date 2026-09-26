from pathlib import Path

import pytest

from ahos.character_memory import CharacterBibleStore, CharacterProfile
from ahos.core_cast_voice_catalog import CORE_CAST_VOICE_SPECS
from ahos.voice_continuity import VoiceContinuityStore
from ahos.voice_enrollment import VoiceEnrollmentStore
from ahos.voice_readiness import CoreCastVoiceReadinessAuditor, export_voice_readiness


SHA = "a" * 64


def stores(tmp_path: Path):
    characters = CharacterBibleStore(tmp_path / "characters.db")
    for spec in CORE_CAST_VOICE_SPECS:
        characters.upsert_profile(
            CharacterProfile(spec.character_id, spec.display_name, spec.role, age_stage=spec.age_stage),
            author="test", reason="seed",
        )
    voices = VoiceContinuityStore(tmp_path / "voices.db", character_store=characters)
    enrollments = VoiceEnrollmentStore(
        tmp_path / "enrollments.db", character_store=characters, voice_store=voices,
    )
    return enrollments


def enroll(store, character_id, language):
    store.enroll(
        character_id=character_id, language=language,
        provider_id="chatterbox-multilingual", voice_id=f"{character_id}-{language}-v1",
        speaking_style="canonical age-appropriate studio voice",
        reference_audio_uri=f"private://voices/{character_id}/{language}.wav",
        reference_sha256=SHA, reference_origin="synthetic", rights_confirmed=True,
        speaker_consent_confirmed=False, human_similarity_approved=True, owner_approved=True,
    )


def test_empty_store_reports_exact_missing_matrix_and_exempts_infants(tmp_path):
    report = CoreCastVoiceReadinessAuditor(stores(tmp_path)).audit(required_languages=("tr", "de"))
    assert report.ready is False
    assert len(report.cells) == 32
    assert len(report.missing) == 28
    assert all(not cell.required for cell in report.cells if cell.character_id in {"medine", "ramin"})


def test_all_required_core_cast_enrollments_are_ready_and_exportable(tmp_path):
    store = stores(tmp_path)
    for spec in CORE_CAST_VOICE_SPECS:
        if spec.speech_mode not in {"infant_vocalization", "animal_vocalization"}:
            for language in ("tr", "de"):
                enroll(store, spec.character_id, language)
    report = CoreCastVoiceReadinessAuditor(store).audit(required_languages=("tr", "de"))
    assert report.ready is True
    assert report.missing == ()
    output = export_voice_readiness(report, tmp_path / "report.json")
    assert report.report_hash in output.read_text(encoding="utf-8")


def test_one_missing_language_fails_closed(tmp_path):
    store = stores(tmp_path)
    enroll(store, "aden", "tr")
    report = CoreCastVoiceReadinessAuditor(store).audit(
        cast=(CORE_CAST_VOICE_SPECS[0],), required_languages=("tr", "de"),
    )
    assert report.ready is False
    assert report.missing == ("aden:de",)


@pytest.mark.parametrize("languages", [(), ("tr", "tr")])
def test_invalid_language_matrix_is_rejected(tmp_path, languages):
    with pytest.raises(ValueError):
        CoreCastVoiceReadinessAuditor(stores(tmp_path)).audit(required_languages=languages)
