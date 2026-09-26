from pathlib import Path

import pytest

from ahos.multilingual_audio_package import AudioPackageAsset, MultilingualAudioPackager
from ahos.kurmanji_quality import KurmanjiLineReview, KurmanjiQualityGate
from ahos.music_sfx_supervision import MusicSfxSupervisor, SoundAssetEvidence, SoundCue
from ahos.studio_acceptance import AcceptancePreflightError, StudioAcceptancePreflight
from ahos.voice_readiness import VoiceReadinessCell, VoiceReadinessReport
from ahos.voice_quality import VoiceQualityReport


LANGUAGES = ("tr", "ku-latn", "de", "ar", "fr", "es", "en")
SHA = "a" * 64


def audio_package(episode_id="S01E001", omit_language=None):
    assets = [
        AudioPackageAsset("music", "music_stem", "private://music.wav", SHA),
        AudioPackageAsset("sfx", "sfx_stem", "private://sfx.wav", SHA),
    ]
    for language in LANGUAGES:
        if language == omit_language:
            continue
        assets.extend((
            AudioPackageAsset(f"mix:{language}", "final_mix", f"private://{language}.wav", SHA, language, 480),
            AudioPackageAsset(f"sub:{language}", "subtitle", f"private://{language}.srt", SHA, language, 480),
        ))
    return MultilingualAudioPackager().build(
        episode_id=episode_id,
        episode_duration_seconds=480,
        speaking_character_ids=("aden",),
        canonical_voice_enrollments=(("aden", language) for language in LANGUAGES),
        assets=tuple(assets),
    )


def sound_package(episode_id="S01E001", approved=True):
    assets = (
        SoundAssetEvidence("music", "music", "private://music.wav", SHA, "private://rights/music.json", "CC-BY-4.0", "AHOS Studio", approved),
        SoundAssetEvidence("sfx", "sfx", "private://sfx.wav", SHA, "private://rights/sfx.json", "CC-BY-4.0", "AHOS Studio", approved),
    )
    cues = (
        SoundCue("music-1", "scene-1", "music", "music", 0, 480, "Episode score", -8, approved, approved),
        SoundCue("sfx-1", "scene-1", "sfx", "sfx", 1, 2, "Story action", -4, approved, approved),
    )
    return MusicSfxSupervisor().build(
        episode_id=episode_id, episode_duration_seconds=480, assets=assets, cues=cues,
    )


def voice_report(ready=True):
    cell = VoiceReadinessCell(
        "aden", "tr", "speech", True, ready, 1 if ready else None,
        SHA if ready else None, "canonical enrollment present" if ready else "missing",
    )
    return VoiceReadinessReport(("tr",), (cell,), "b" * 64)


def kurmanji_report(ready=True):
    return KurmanjiQualityGate().evaluate((
        KurmanjiLineReview(
            "L1", "Silav! Tu dixwazî bi min re bilîzî?", "native-reviewer-01",
            ready, ready, ready, ready,
        ),
    ))


def rendered_voice_report(ready=True):
    return VoiceQualityReport(
        clips=(), expected_pairs=("aden:tr",),
        missing_pairs=() if ready else ("aden:tr",),
        ready=ready, report_hash="c" * 64,
    )


def backlog(status6="completed"):
    return {
        "tasks": [
            {"id": f"STUDIO-{n:03d}", "status": status6 if n == 6 else "completed"}
            for n in range(1, 9)
        ]
    }


def evaluate(tmp_path: Path, **overrides):
    artifact = tmp_path / "proof.json"
    artifact.write_text("{}", encoding="utf-8")
    values = {
        "episode_id": "S01E001",
        "backlog": backlog(),
        "required_artifacts": (artifact,),
        "multilingual_audio_package": audio_package(),
        "sound_supervision_package": sound_package(),
        "voice_readiness_report": voice_report(),
        "voice_similarity_approved": True,
        "owner_approved": True,
        "execution_enabled": True,
        "paid_provider_enabled": True,
        "paid_execution_requested": True,
        "publish_requested": False,
        "kurmanji_quality_report": kurmanji_report(),
        "voice_quality_report": rendered_voice_report(),
    }
    values.update(overrides)
    return StudioAcceptancePreflight().evaluate(**values)


def test_every_gate_must_pass_before_paid_execution(tmp_path: Path):
    result = evaluate(tmp_path)
    assert result.ready_for_paid_execution is True
    assert all(g.passed for g in result.gates)


def test_studio_006_in_progress_blocks_acceptance(tmp_path: Path):
    result = evaluate(tmp_path, backlog=backlog("in_progress"))
    assert result.ready_for_paid_execution is False
    assert "STUDIO-006" in next(g.message for g in result.gates if g.gate_id == "studio-roadmap")


@pytest.mark.parametrize("field", ["voice_similarity_approved", "owner_approved", "execution_enabled", "paid_provider_enabled"])
def test_each_protected_gate_fails_closed(tmp_path: Path, field: str):
    result = evaluate(tmp_path, **{field: False})
    assert result.ready_for_paid_execution is False


def test_preflight_does_not_spend_without_execution_request(tmp_path: Path):
    result = evaluate(tmp_path, paid_execution_requested=False)
    assert result.ready_for_paid_execution is False
    assert result.paid_execution_requested is False


def test_publish_request_is_blocked(tmp_path: Path):
    result = evaluate(tmp_path, publish_requested=True)
    assert result.ready_for_paid_execution is False


def test_missing_artifact_blocks_acceptance(tmp_path: Path):
    result = evaluate(tmp_path, required_artifacts=(tmp_path / "missing.json",))
    assert result.ready_for_paid_execution is False


@pytest.mark.parametrize("package", [None, audio_package(omit_language="ar")])
def test_multilingual_audio_evidence_fails_closed(tmp_path: Path, package):
    result = evaluate(tmp_path, multilingual_audio_package=package)
    assert result.ready_for_paid_execution is False
    gate = next(g for g in result.gates if g.gate_id == "multilingual-audio-package")
    assert gate.passed is False


def test_wrong_episode_audio_package_is_rejected(tmp_path: Path):
    result = evaluate(tmp_path, multilingual_audio_package=audio_package("S01E002"))
    assert result.ready_for_paid_execution is False
    gate = next(g for g in result.gates if g.gate_id == "multilingual-audio-package")
    assert "mismatch" in gate.message


@pytest.mark.parametrize("package", [None, sound_package(approved=False)])
def test_music_sfx_supervision_fails_closed(tmp_path: Path, package):
    result = evaluate(tmp_path, sound_supervision_package=package)
    assert result.ready_for_paid_execution is False
    gate = next(g for g in result.gates if g.gate_id == "music-sfx-supervision")
    assert gate.passed is False


def test_wrong_episode_sound_package_is_rejected(tmp_path: Path):
    result = evaluate(tmp_path, sound_supervision_package=sound_package("S01E002"))
    assert result.ready_for_paid_execution is False
    gate = next(g for g in result.gates if g.gate_id == "music-sfx-supervision")
    assert "mismatch" in gate.message


@pytest.mark.parametrize("report", [None, voice_report(False)])
def test_canonical_voice_readiness_fails_closed(tmp_path: Path, report):
    result = evaluate(tmp_path, voice_readiness_report=report)
    assert result.ready_for_paid_execution is False
    gate = next(g for g in result.gates if g.gate_id == "canonical-voice-readiness")
    assert gate.passed is False


@pytest.mark.parametrize("report", [None, kurmanji_report(False)])
def test_kurmanji_quality_evidence_fails_closed(tmp_path: Path, report):
    result = evaluate(tmp_path, kurmanji_quality_report=report)
    assert result.ready_for_paid_execution is False
    gate = next(g for g in result.gates if g.gate_id == "kurmanji-localization-quality")
    assert gate.passed is False


@pytest.mark.parametrize("report", [None, rendered_voice_report(False)])
def test_rendered_voice_quality_evidence_fails_closed(tmp_path: Path, report):
    result = evaluate(tmp_path, voice_quality_report=report)
    assert result.ready_for_paid_execution is False
    gate = next(g for g in result.gates if g.gate_id == "rendered-voice-quality")
    assert gate.passed is False


def test_invalid_backlog_fails_closed(tmp_path: Path):
    with pytest.raises(AcceptancePreflightError):
        evaluate(tmp_path, backlog={})
