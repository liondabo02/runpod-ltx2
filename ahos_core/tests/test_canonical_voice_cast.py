from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from ahos.canonical_voice_cast import CanonicalVoiceCastBinder, CanonicalVoiceCastError
from ahos.character_memory import CharacterBibleStore, CharacterProfile
from ahos.voice_continuity import VoiceContinuityStore
from ahos.voice_enrollment import VoiceEnrollmentStore


def setup_binder(tmp_path: Path):
    lab = tmp_path / "lab"
    audio = lab / "audio" / "aden" / "aden-B.wav"
    audio.parent.mkdir(parents=True)
    audio.write_bytes(b"studio-owned synthetic wav")
    sha = hashlib.sha256(audio.read_bytes()).hexdigest()
    (lab / "OWNER-VOICE-APPROVALS.json").write_text(json.dumps({
        "schema": "ahos.owner-voice-approvals.v1",
        "approvals": {"aden": {
            "character_id": "aden",
            "candidate_id": "aden-B",
            "audio_path": "audio/aden/aden-B.wav",
            "sha256": sha,
            "reference_origin": "synthetic",
            "rights_confirmed": True,
            "owner_approved": True,
            "owner_selection_delegated": True,
            "selection": {"direction": "young, warm, playful"},
        }},
    }), encoding="utf-8")
    (lab / "VOICE-CANDIDATES.json").write_text(json.dumps({
        "characters": [
            {"character_id": "aden", "speech_mode": "speech"},
            {"character_id": "ramin", "speech_mode": "infant_vocalization"},
        ]
    }), encoding="utf-8")
    characters = CharacterBibleStore(tmp_path / "characters.db")
    characters.upsert_profile(
        CharacterProfile(character_id="aden", display_name="Aden", canonical_role="lead", age_stage="child"),
        author="test", reason="seed",
    )
    voices = VoiceContinuityStore(tmp_path / "voices.db", character_store=characters)
    enrollments = VoiceEnrollmentStore(
        tmp_path / "enrollments.db", character_store=characters, voice_store=voices
    )
    return CanonicalVoiceCastBinder(
        lab, character_store=characters, voice_store=voices, enrollment_store=enrollments
    ), enrollments, audio


def test_bind_hash_locks_all_supported_languages_and_is_idempotent(tmp_path):
    binder, enrollments, _ = setup_binder(tmp_path)
    first = binder.bind()
    assert len(first["bound"]) == 7
    assert first["infant_vocalization_library_required"] == ["ramin"]
    assert first["pending_language_bindings"] == {}
    assert first["provider_by_language"]["ku-latn"] == "openvoice-v2-tone-transfer"
    assert enrollments.get("aden", "ku-latn").provider_id == "openvoice-v2-tone-transfer"
    assert binder.readiness_path.is_file()
    assert enrollments.get("aden", "tr").human_similarity_approved is False

    second = binder.bind()
    assert second["bound"] == []
    assert len(second["unchanged"]) == 7
    assert len(enrollments.history("aden", "tr")) == 1


def test_bind_rejects_tampered_audio(tmp_path):
    binder, _, audio = setup_binder(tmp_path)
    audio.write_bytes(b"tampered")
    with pytest.raises(CanonicalVoiceCastError, match="missing or changed"):
        binder.bind()


def test_bind_refuses_silent_voice_override(tmp_path):
    binder, _, _ = setup_binder(tmp_path)
    binder.bind(languages=("tr",))
    ledger = json.loads(binder.approvals_path.read_text(encoding="utf-8"))
    ledger["approvals"]["aden"]["candidate_id"] = "aden-C"
    binder.approvals_path.write_text(json.dumps(ledger), encoding="utf-8")
    with pytest.raises(CanonicalVoiceCastError, match="allow-versioned-override"):
        binder.bind(languages=("tr",))


def test_kurmanji_is_bound_only_to_verified_identity_transfer_provider(tmp_path):
    binder, enrollments, _ = setup_binder(tmp_path)
    report = binder.bind(languages=("ku-latn",))
    assert report["provider_by_language"] == {
        "ku-latn": "openvoice-v2-tone-transfer"
    }
    assert enrollments.get("aden", "ku-latn").provider_id == "openvoice-v2-tone-transfer"
