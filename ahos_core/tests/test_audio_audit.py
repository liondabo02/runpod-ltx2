"""Ses varlığı denetimi — gerçek dosyaları değiştirmez, sentetik örnekle test eder."""
from __future__ import annotations

import math
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))


def _wav(path: Path, *, seconds: float = 1.0, freq: float = 440.0, silent: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rate = 16000
    frames = int(rate * seconds)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        if silent:
            sample = b"\x00\x00" * frames
        else:
            amplitude = 8000
            sample = b"".join(
                int(amplitude * math.sin(2 * math.pi * freq * index / rate)).to_bytes(2, "little", signed=True)
                for index in range(frames))
        handle.writeframes(sample)


def test_clean_assets_have_no_issues(tmp_path):
    import audio_asset_audit

    root = tmp_path / "audio"
    _wav(root / "aden" / "reference-en.wav")
    _wav(root / "aden" / "tr.wav", freq=220.0)

    report = audio_asset_audit.audit(root)

    assert report["summary"]["folders"] == 1
    assert report["summary"]["files"] == 2
    assert report["summary"]["issues"] == 0


def test_silent_missing_and_short_assets_are_flagged(tmp_path):
    import audio_asset_audit

    root = tmp_path / "audio"
    _wav(root / "aden" / "reference-en.wav", silent=True)
    _wav(root / "aden" / "tr.wav", seconds=0.1)
    _wav(root / "kaan" / "reference-en.wav")

    report = audio_asset_audit.audit(root)
    issues = {entry["character_id"]: entry["issues"] for entry in report["characters"]}

    assert any(issue.startswith("silent") for issue in issues["aden"])
    assert any(issue.startswith("too_short") for issue in issues["aden"])
    assert any(issue.startswith("missing") for issue in issues["kaan"])
    assert report["summary"]["issues"] >= 3
