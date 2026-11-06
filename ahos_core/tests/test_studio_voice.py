"""Ses hattı: kanal dizme, sessizlik ölçümü ve sesli bölüm kabulü."""

from __future__ import annotations

import array
import math
import wave
from pathlib import Path

import pytest

from ahos.studio_2d import Episode, Line, Scene, render_episode
from ahos.studio_qa import verify_episode
from ahos.studio_voice import build_track, list_voices, rms, synthesize_wav, wav_duration

RATE = 22050


def _tone(path: Path, seconds: float, freq: float = 440.0, amp: int = 8000) -> Path:
    frames = int(seconds * RATE)
    samples = array.array("h")
    for index in range(frames):
        samples.append(int(amp * math.sin(2 * math.pi * freq * index / RATE)))
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(RATE)
        handle.writeframes(samples.tobytes())
    return path


def test_build_track_places_clips_at_offsets(tmp_path):
    a = _tone(tmp_path / "a.wav", 0.5)
    b = _tone(tmp_path / "b.wav", 0.5)
    track = build_track([(a, 0.0, 0.5), (b, 1.5, 0.5)], 2.0, tmp_path / "track.wav")

    assert abs(wav_duration(track) - 2.0) < 0.05
    assert rms(track) > 0

    with wave.open(str(track), "rb") as handle:
        frames = array.array("h")
        frames.frombytes(handle.readframes(handle.getnframes()))

    def _energy(seconds: float) -> float:
        start = int(seconds * RATE)
        chunk = frames[start:start + int(0.2 * RATE)]
        return sum(abs(v) for v in chunk) / max(1, len(chunk))

    assert _energy(0.1) > 500        # ilk klip
    assert _energy(1.0) < 50         # arada sessizlik
    assert _energy(1.6) > 500        # ikinci klip


def test_silence_has_no_energy(tmp_path):
    silent = build_track([], 1.0, tmp_path / "silent.wav")
    assert rms(silent) == 0.0


def test_envelope_follows_the_audio(tmp_path):
    """Dudak senkronu: sesin olduğu yerde zarf yüksek, sessizlikte sıfır."""

    from ahos.studio_voice import amplitude_envelope

    loud = _tone(tmp_path / "loud.wav", 0.5)
    track = build_track([(loud, 0.0, 0.5)], 1.0, tmp_path / "envelope.wav")
    envelope = amplitude_envelope(track, fps=10, total_frames=10)

    assert len(envelope) == 10
    assert max(envelope[:4]) > 0.5          # konuşma bölgesi
    assert max(envelope[7:]) < 0.2          # sessizlik bölgesi
    assert all(0.0 <= value <= 1.0 for value in envelope)


def test_edge_voice_mapping_per_character():
    """Aden kadın, Kaan erkek sesi alır; bilinmeyen dilde ses yok."""

    from ahos.studio_voice import edge_voice

    assert edge_voice("tr", "aden") == "tr-TR-EmelNeural"
    assert edge_voice("tr", "kaan") == "tr-TR-AhmetNeural"
    assert edge_voice("tr-TR", "bilinmeyen") == "tr-TR-EmelNeural"
    assert edge_voice("xx", "aden") is None


def test_engine_follows_explicit_override_and_language(monkeypatch):
    from ahos.studio_voice import engine_for

    monkeypatch.delenv("AHOS_VOICE_ENGINE", raising=False)
    assert engine_for("tr") == "edge"        # Türkçe için nöral ses var
    monkeypatch.setenv("AHOS_VOICE_ENGINE", "sapi")
    assert engine_for("tr") == "sapi"        # açık istek her zaman kazanır


@pytest.mark.skipif(not list_voices(), reason="kurulu SAPI sesi yok")
def test_voiced_episode_passes_the_gate(tmp_path):
    voice = list_voices()[0]
    line = synthesize_wav("merhaba dunya", tmp_path / "line.wav", voice=voice)
    assert wav_duration(line) > 0.2

    episode = Episode(
        title="ses testi",
        scenes=[Scene("s1", "sahne", "day", ["aden"], [Line("s1", "aden", "merhaba", 1.5)])],
    )
    track = build_track([(line, 0.0, wav_duration(line))], episode.duration() + 0.3,
                        tmp_path / "episode.wav")
    manifest = render_episode(episode, tmp_path / "out", voice=voice.name, audio=track)

    report = verify_episode(
        manifest["video"],
        expected_scenes=1,
        expected_duration=manifest["duration_seconds"],
        subtitles=manifest["subtitles"],
        expects_audio=True,
        expected_cuts=0,
    )
    assert report["passed"] is True, report
    assert report["measurements"]["audio_streams"] == 1
    assert report["measurements"]["audio"]["rms"] > 120
