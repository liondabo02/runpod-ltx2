import io
import math
import struct
import wave

import pytest

from ahos.voice_audio_quality import (
    VoiceAudioQualityError,
    inspect_wav,
    prepare_openvoice_reference,
    validate_generated_voice,
)


def wav(seconds: float, *, rate: int = 16_000, amplitude: int = 6000) -> bytes:
    frames = bytearray()
    for index in range(round(seconds * rate)):
        sample = round(amplitude * math.sin(2 * math.pi * 220 * index / rate))
        frames.extend(struct.pack("<h", sample))
    output = io.BytesIO()
    with wave.open(output, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(rate)
        target.writeframes(bytes(frames))
    return output.getvalue()


def test_short_reference_is_automatically_extended_without_format_change():
    prepared, quality, changed = prepare_openvoice_reference(wav(2.5))
    assert changed is True
    assert quality.duration_seconds == 8.0
    assert inspect_wav(prepared).sample_rate_hz == 16_000


def test_long_enough_reference_is_not_rewritten():
    original = wav(9.0)
    prepared, quality, changed = prepare_openvoice_reference(original)
    assert prepared == original
    assert changed is False
    assert quality.duration_seconds == 9.0


def test_silent_reference_and_bad_generated_audio_fail_closed():
    with pytest.raises(VoiceAudioQualityError, match="silent"):
        prepare_openvoice_reference(wav(2.0, amplitude=0))
    with pytest.raises(VoiceAudioQualityError, match="too short"):
        validate_generated_voice(wav(0.1))
