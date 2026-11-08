"""Medya teslim hattı testleri: gerçek üretim küçük ölçekte."""
from __future__ import annotations

import math
import wave

import numpy as np
import pytest

from ahos import media_delivery as md


def _tone(path, seconds=1.0, rate=48000):
    t = np.arange(int(seconds * rate)) / rate
    signal = (0.2 * np.sin(2 * math.pi * 440 * t) * 32767).astype("<i2")
    stereo = np.repeat(signal[:, None], 2, axis=1).reshape(-1)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(stereo.tobytes())


def test_small_video_is_produced_and_verified(tmp_path):
    frames = tmp_path / "frames"
    info = md.render_frames(frames, seconds=0.5, fps=12, width=320, height=180)
    assert info["frames"] == 6 and len(list(frames.glob("*.png"))) == 6

    narration = tmp_path / "tone.wav"
    _tone(narration)
    audio = tmp_path / "audio.wav"
    md.build_audio(narration, audio, seconds=0.5)
    assert audio.stat().st_size > 1000

    video = tmp_path / "out.mp4"
    md.mux(frames, audio, video, fps=12, seconds=0.5)
    result = md.verify_video(video, seconds=0.5, fps=12, width=320, height=180)
    assert result["ok"] is True, result["checks"]
    assert result["checks"]["audio_stream"] and result["checks"]["video_stream"]
    assert result["checks"]["not_blank"] and result["checks"]["audio_not_silent"]


def test_missing_file_fails_closed(tmp_path):
    result = md.verify_video(tmp_path / "yok.mp4", seconds=1, fps=24,
                             width=1920, height=1080)
    assert result["ok"] is False
    assert result["checks"]["exists"] is False


def test_srt_format():
    text = md.srt([(0.0, 1.5, "Merhaba"), (1.5, 3.0, "Dünya")])
    assert "00:00:00,000 --> 00:00:01,500" in text
    assert text.strip().endswith("Dünya")
