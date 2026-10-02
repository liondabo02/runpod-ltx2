import io
import math
import struct
import wave

import pytest

from ahos.voice_quality import (
    ProfessionalVoiceQualityGate,
    VoiceClipEvidence,
    VoiceQualityError,
    analyze_wav,
)


def wav_bytes(*, amplitude=0.2, seconds=1.0, rate=24000, dc=0.0):
    samples = []
    for index in range(int(rate * seconds)):
        value = dc + amplitude * math.sin(2 * math.pi * 440 * index / rate)
        samples.append(max(-32768, min(32767, int(value * 32767))))
    output = io.BytesIO()
    with wave.open(output, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(rate)
        target.writeframes(b"".join(struct.pack("<h", sample) for sample in samples))
    return output.getvalue()


def evidence(**overrides):
    values = dict(
        character_id="aden", language="tr", line_id="L1", wav_bytes=wav_bytes(),
        transcript_verified=True, native_language_approved=True,
        character_fit_approved=True, speaker_similarity_approved=True,
    )
    values.update(overrides)
    return VoiceClipEvidence(**values)


def test_valid_voice_passes_objective_and_human_quality_gate():
    report = ProfessionalVoiceQualityGate().evaluate(
        (evidence(),), expected_character_languages=(("aden", "tr"),),
    )
    assert report.ready is True
    assert report.clips[0].metrics.sample_rate_hz == 24000
    assert len(report.report_hash) == 64


@pytest.mark.parametrize(
    "field,issue",
    [
        ("transcript_verified", "transcript-not-verified"),
        ("native_language_approved", "native-listening-not-approved"),
        ("character_fit_approved", "character-fit-not-approved"),
        ("speaker_similarity_approved", "speaker-similarity-not-approved"),
    ],
)
def test_missing_human_approval_fails_closed(field, issue):
    report = ProfessionalVoiceQualityGate().evaluate(
        (evidence(**{field: False}),), expected_character_languages=(("aden", "tr"),),
    )
    assert report.ready is False
    assert issue in report.clips[0].blocking_issues


def test_low_sample_rate_clipping_and_missing_coverage_fail():
    report = ProfessionalVoiceQualityGate().evaluate(
        (evidence(wav_bytes=wav_bytes(amplitude=1.5, rate=16000)),),
        expected_character_languages=(("aden", "tr"), ("harun", "tr")),
    )
    assert report.ready is False
    assert "sample-rate-below-24khz" in report.clips[0].blocking_issues
    assert "clipping-detected" in report.clips[0].blocking_issues
    assert report.missing_pairs == ("harun:tr",)


def test_invalid_wav_and_duplicate_evidence_are_rejected_or_blocked():
    report = ProfessionalVoiceQualityGate().evaluate(
        (evidence(wav_bytes=b"not-wave"),), expected_character_languages=(("aden", "tr"),),
    )
    assert report.ready is False
    assert report.clips[0].blocking_issues[0].startswith("invalid-audio:")
    with pytest.raises(VoiceQualityError):
        ProfessionalVoiceQualityGate().evaluate(
            (evidence(), evidence()), expected_character_languages=(("aden", "tr"),),
        )


def test_analyzer_is_deterministic():
    payload = wav_bytes()
    assert analyze_wav(payload) == analyze_wav(payload)
