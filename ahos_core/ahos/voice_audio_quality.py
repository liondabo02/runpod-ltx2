from __future__ import annotations

import io
import math
import struct
import wave
from dataclasses import asdict, dataclass


class VoiceAudioQualityError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class WavQuality:
    duration_seconds: float
    sample_rate_hz: int
    channels: int
    sample_width_bytes: int
    peak: float
    rms: float
    clipping_ratio: float
    silence_ratio: float

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def inspect_wav(audio: bytes, *, label: str = "audio") -> WavQuality:
    try:
        with wave.open(io.BytesIO(audio), "rb") as source:
            channels = source.getnchannels()
            sample_width = source.getsampwidth()
            sample_rate = source.getframerate()
            frame_count = source.getnframes()
            frames = source.readframes(frame_count)
    except (EOFError, wave.Error) as exc:
        raise VoiceAudioQualityError(f"{label} is not a valid WAV: {exc}") from exc
    if channels not in {1, 2}:
        raise VoiceAudioQualityError(f"{label} must have one or two channels")
    if sample_width != 2:
        raise VoiceAudioQualityError(f"{label} must use 16-bit PCM")
    if sample_rate < 16_000:
        raise VoiceAudioQualityError(f"{label} sample rate must be at least 16000 Hz")
    if frame_count <= 0 or not frames:
        raise VoiceAudioQualityError(f"{label} is empty")
    samples = struct.unpack(f"<{len(frames) // 2}h", frames)
    peak = max(abs(value) for value in samples) / 32768.0
    rms = math.sqrt(sum(value * value for value in samples) / len(samples)) / 32768.0
    clipping = sum(abs(value) >= 32700 for value in samples) / len(samples)
    silence = sum(abs(value) < 180 for value in samples) / len(samples)
    return WavQuality(
        duration_seconds=round(frame_count / sample_rate, 4),
        sample_rate_hz=sample_rate,
        channels=channels,
        sample_width_bytes=sample_width,
        peak=round(peak, 6),
        rms=round(rms, 6),
        clipping_ratio=round(clipping, 8),
        silence_ratio=round(silence, 6),
    )


def prepare_openvoice_reference(
    audio: bytes, *, minimum_seconds: float = 8.0, maximum_seconds: float = 30.0,
) -> tuple[bytes, WavQuality, bool]:
    """Return a model-safe reference, repeating short approved material if needed.

    Repetition preserves the approved speaker identity and avoids synthesizing or
    silently substituting a different character voice.
    """
    if minimum_seconds <= 0 or maximum_seconds < minimum_seconds:
        raise ValueError("invalid OpenVoice reference duration limits")
    quality = inspect_wav(audio, label="OpenVoice reference")
    if quality.rms < 0.004:
        raise VoiceAudioQualityError("OpenVoice reference signal is effectively silent")
    if quality.clipping_ratio > 0.01:
        raise VoiceAudioQualityError("OpenVoice reference is excessively clipped")
    if quality.silence_ratio > 0.80:
        raise VoiceAudioQualityError("OpenVoice reference contains excessive silence")

    with wave.open(io.BytesIO(audio), "rb") as source:
        params = source.getparams()
        frames = source.readframes(source.getnframes())
    target_frames = min(
        math.ceil(minimum_seconds * quality.sample_rate_hz),
        math.floor(maximum_seconds * quality.sample_rate_hz),
    )
    current_frames = len(frames) // (quality.channels * quality.sample_width_bytes)
    if current_frames >= target_frames:
        return audio, quality, False
    repetitions = math.ceil(target_frames / current_frames)
    prepared_frames = (frames * repetitions)[: target_frames * quality.channels * quality.sample_width_bytes]
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as target:
        target.setparams(params)
        target.writeframes(prepared_frames)
    prepared = buffer.getvalue()
    return prepared, inspect_wav(prepared, label="prepared OpenVoice reference"), True


def validate_generated_voice(audio: bytes, *, minimum_seconds: float = 0.20) -> WavQuality:
    quality = inspect_wav(audio, label="generated voice")
    if quality.duration_seconds < minimum_seconds:
        raise VoiceAudioQualityError("generated voice is too short")
    if quality.rms < 0.003:
        raise VoiceAudioQualityError("generated voice signal is effectively silent")
    if quality.clipping_ratio > 0.02:
        raise VoiceAudioQualityError("generated voice is excessively clipped")
    if quality.silence_ratio > 0.90:
        raise VoiceAudioQualityError("generated voice contains excessive silence")
    return quality


__all__ = [
    "VoiceAudioQualityError", "WavQuality", "inspect_wav",
    "prepare_openvoice_reference", "validate_generated_voice",
]
