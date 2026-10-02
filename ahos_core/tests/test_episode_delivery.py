from dataclasses import replace

import pytest

from ahos.episode_delivery import EpisodeDeliveryError, EpisodeDeliveryGate, PRODUCTION_LANGUAGES
from ahos.kurmanji_quality import KurmanjiLineReview, KurmanjiQualityGate
from ahos.multilingual_audio_package import AudioPackageAsset, MultilingualAudioPackager
from ahos.studio_acceptance import AcceptanceGate, AcceptancePreflight
from ahos.voice_quality import VoiceClipMetrics, VoiceClipQuality, VoiceQualityReport


SHA = "a" * 64


def audio_package():
    assets = [
        AudioPackageAsset("music", "music_stem", "private://music.wav", SHA),
        AudioPackageAsset("sfx", "sfx_stem", "private://sfx.wav", SHA),
    ]
    for language in PRODUCTION_LANGUAGES:
        assets.extend((
            AudioPackageAsset(f"mix:{language}", "final_mix", f"private://{language}.wav", SHA, language, 480),
            AudioPackageAsset(f"sub:{language}", "subtitle", f"private://{language}.srt", SHA, language),
        ))
    return MultilingualAudioPackager().build(
        episode_id="S01E001",
        episode_duration_seconds=480,
        speaking_character_ids=("aden", "kaan"),
        canonical_voice_enrollments=(
            (speaker, language) for speaker in ("aden", "kaan") for language in PRODUCTION_LANGUAGES
        ),
        assets=assets,
        required_languages=PRODUCTION_LANGUAGES,
    )


def voice_report(*, omit=None):
    pairs = tuple(
        sorted(
            f"{speaker}:{language}"
            for speaker in ("aden", "kaan")
            for language in PRODUCTION_LANGUAGES
            if f"{speaker}:{language}" != omit
        )
    )
    clips = tuple(
        VoiceClipQuality(
            *pair.split(":"),
            "sample-line",
            VoiceClipMetrics(24000, 1, 2, 1.0, -3.0, -18.0, 0.0, 0.1, 0.0, "d" * 64),
            (),
            True,
        )
        for pair in pairs
    )
    return VoiceQualityReport(clips, pairs, (), True, "b" * 64)


def kurmanji_report():
    return KurmanjiQualityGate().evaluate((
        KurmanjiLineReview("L1", "Silav Kaan, em ê niha bilîzin.", "reviewer-01", True, True, True, True),
    ))


def preflight(*, episode_id="S01E001", publish=False):
    gates = (AcceptanceGate("all", True, True, "passed"),)
    return AcceptancePreflight(episode_id, gates, True, True, publish)


def evaluate(**overrides):
    values = {
        "episode_id": "S01E001",
        "speaking_character_ids": ("aden", "kaan"),
        "audio_package": audio_package(),
        "voice_quality_report": voice_report(),
        "kurmanji_quality_report": kurmanji_report(),
        "acceptance_preflight": preflight(),
        "picture_master_sha256": "c" * 64,
    }
    values.update(overrides)
    return EpisodeDeliveryGate().evaluate(**values)


def test_professional_episode_delivery_evidence_passes_end_to_end():
    report = evaluate()
    assert report.release_candidate_ready is True
    assert len(report.checks) == 7
    assert len(report.evidence_hash) == 64
    assert report.to_payload()["schema"] == "ahos.episode-delivery-evidence.v1"


def test_missing_voice_language_pair_blocks_delivery():
    report = evaluate(voice_quality_report=voice_report(omit="kaan:ku-latn"))
    assert report.release_candidate_ready is False
    assert next(c for c in report.checks if c.check_id == "rendered-voice-coverage").passed is False


def test_declared_coverage_without_rendered_clip_evidence_blocks_delivery():
    report = evaluate(voice_quality_report=replace(voice_report(), clips=()))
    assert report.release_candidate_ready is False
    assert next(c for c in report.checks if c.check_id == "rendered-voice-coverage").passed is False


def test_noncanonical_language_order_blocks_delivery():
    package = replace(audio_package(), required_languages=tuple(reversed(PRODUCTION_LANGUAGES)))
    report = evaluate(audio_package=package)
    assert next(c for c in report.checks if c.check_id == "canonical-seven-languages").passed is False


@pytest.mark.parametrize(
    "override",
    (
        {"acceptance_preflight": preflight(episode_id="S01E999")},
        {"acceptance_preflight": preflight(publish=True)},
        {"picture_master_sha256": "not-a-digest"},
    ),
)
def test_identity_publish_and_integrity_fail_closed(override):
    assert evaluate(**override).release_candidate_ready is False


def test_speaking_cast_is_required():
    with pytest.raises(EpisodeDeliveryError, match="speaking character"):
        evaluate(speaking_character_ids=())
