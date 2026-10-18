from __future__ import annotations

import hashlib
import io
import math
import wave
from dataclasses import dataclass
from typing import Iterable


class VoiceQualityError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class VoiceClipEvidence:
    character_id: str
    language: str
    line_id: str
    wav_bytes: bytes
    transcript_verified: bool
    native_language_approved: bool
    character_fit_approved: bool
    speaker_similarity_approved: bool


@dataclass(frozen=True, slots=True)
class VoiceClipMetrics:
    sample_rate_hz: int
    channels: int
    sample_width_bytes: int
    duration_seconds: float
    peak_dbfs: float
    rms_dbfs: float
    clipping_ratio: float
    silence_ratio: float
    dc_offset_ratio: float
    sha256: str


@dataclass(frozen=True, slots=True)
class VoiceClipQuality:
    character_id: str
    language: str
    line_id: str
    metrics: VoiceClipMetrics | None
    blocking_issues: tuple[str, ...]
    ready: bool


@dataclass(frozen=True, slots=True)
class VoiceQualityReport:
    clips: tuple[VoiceClipQuality, ...]
    expected_pairs: tuple[str, ...]
    missing_pairs: tuple[str, ...]
    ready: bool
    report_hash: str


def _dbfs(value: float) -> float:
    return -120.0 if value <= 0 else 20.0 * math.log10(value)


def _decode_pcm(raw: bytes, sample_width: int) -> tuple[int, ...]:
    if sample_width not in {1, 2, 3, 4}:
        raise VoiceQualityError(f"unsupported PCM sample width: {sample_width}")
    values: list[int] = []
    if sample_width == 1:
        return tuple(byte - 128 for byte in raw)
    for offset in range(0, len(raw), sample_width):
        chunk = raw[offset : offset + sample_width]
        if len(chunk) != sample_width:
            raise VoiceQualityError("truncated PCM frame")
        values.append(int.from_bytes(chunk, "little", signed=True))
    return tuple(values)


def analyze_wav(wav_bytes: bytes) -> VoiceClipMetrics:
    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as source:
            if source.getcomptype() != "NONE":
                raise VoiceQualityError("compressed WAV is not accepted")
            channels = source.getnchannels()
            sample_rate = source.getframerate()
            sample_width = source.getsampwidth()
            frame_count = source.getnframes()
            raw = source.readframes(frame_count)
    except (wave.Error, EOFError) as exc:
        raise VoiceQualityError(f"invalid WAV: {exc}") from exc

    if channels not in {1, 2} or sample_rate <= 0 or frame_count <= 0:
        raise VoiceQualityError("WAV must contain mono/stereo PCM audio")
    samples = _decode_pcm(raw, sample_width)
    if not samples:
        raise VoiceQualityError("WAV contains no samples")

    full_scale = float((1 << (sample_width * 8 - 1)) - 1)
    normalized = tuple(sample / full_scale for sample in samples)
    peak = max(abs(sample) for sample in normalized)
    rms = math.sqrt(sum(sample * sample for sample in normalized) / len(normalized))
    clipping_ratio = sum(abs(sample) >= 0.999 for sample in normalized) / len(normalized)
    silence_ratio = sum(abs(sample) <= 0.0031623 for sample in normalized) / len(normalized)
    dc_offset = abs(sum(normalized) / len(normalized))
    return VoiceClipMetrics(
        sample_rate_hz=sample_rate,
        channels=channels,
        sample_width_bytes=sample_width,
        duration_seconds=frame_count / sample_rate,
        peak_dbfs=_dbfs(peak),
        rms_dbfs=_dbfs(rms),
        clipping_ratio=clipping_ratio,
        silence_ratio=silence_ratio,
        dc_offset_ratio=dc_offset,
        sha256=hashlib.sha256(wav_bytes).hexdigest(),
    )


class ProfessionalVoiceQualityGate:
    """Objective signal QA plus mandatory human creative/listening approvals."""

    def evaluate(
        self,
        evidence: Iterable[VoiceClipEvidence],
        *,
        expected_character_languages: Iterable[tuple[str, str]],
    ) -> VoiceQualityReport:
        clips = tuple(evidence)
        expected = tuple(sorted({f"{character}:{language}" for character, language in expected_character_languages}))
        if not expected:
            raise VoiceQualityError("expected character/language coverage is required")

        seen_lines: set[str] = set()
        covered: set[str] = set()
        results: list[VoiceClipQuality] = []
        for clip in clips:
            key = f"{clip.character_id.strip()}:{clip.language.strip().lower()}"
            line_key = f"{key}:{clip.line_id.strip()}"
            if not clip.character_id.strip() or not clip.language.strip() or not clip.line_id.strip():
                raise VoiceQualityError("character_id, language, and line_id are required")
            if line_key in seen_lines:
                raise VoiceQualityError(f"duplicate voice evidence: {line_key}")
            seen_lines.add(line_key)
            covered.add(key)
            issues: list[str] = []
            metrics: VoiceClipMetrics | None = None
            try:
                metrics = analyze_wav(clip.wav_bytes)
            except VoiceQualityError as exc:
                issues.append("invalid-audio:" + str(exc))

            if metrics is not None:
                if metrics.sample_rate_hz < 24000:
                    issues.append("sample-rate-below-24khz")
                if metrics.sample_width_bytes < 2:
                    issues.append("sample-depth-below-16bit")
                if not 0.25 <= metrics.duration_seconds <= 30.0:
                    issues.append("duration-out-of-range")
                if metrics.peak_dbfs > -0.1 or metrics.clipping_ratio > 0.001:
                    issues.append("clipping-detected")
                if not -36.0 <= metrics.rms_dbfs <= -8.0:
                    issues.append("dialogue-level-out-of-range")
                if metrics.silence_ratio > 0.80:
                    issues.append("excessive-silence")
                if metrics.dc_offset_ratio > 0.02:
                    issues.append("dc-offset-detected")

            approvals = (
                (clip.transcript_verified, "transcript-not-verified"),
                (clip.native_language_approved, "native-listening-not-approved"),
                (clip.character_fit_approved, "character-fit-not-approved"),
                (clip.speaker_similarity_approved, "speaker-similarity-not-approved"),
            )
            issues.extend(issue for approved, issue in approvals if not approved)
            results.append(VoiceClipQuality(
                clip.character_id.strip(), clip.language.strip().lower(), clip.line_id.strip(),
                metrics, tuple(issues), not issues,
            ))

        missing = tuple(sorted(set(expected) - covered))
        material = "\n".join(
            [*expected, *missing]
            + [
                f"{item.character_id}:{item.language}:{item.line_id}:"
                f"{item.metrics.sha256 if item.metrics else 'invalid'}:{','.join(item.blocking_issues)}"
                for item in results
            ]
        )
        ready = bool(results) and not missing and all(item.ready for item in results)
        return VoiceQualityReport(
            clips=tuple(results), expected_pairs=expected, missing_pairs=missing,
            ready=ready, report_hash=hashlib.sha256(material.encode("utf-8")).hexdigest(),
        )

