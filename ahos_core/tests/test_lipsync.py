"""Rhubarb lip-sync adaptörü: şema, sıra ve viseme sorgusu."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ahos.lipsync import (RhubarbError, load_visemes, parse_rhubarb,
                          rhubarb_executable, viseme_at)

FIXTURE = {
    "metadata": {"soundFile": "line.wav", "duration": 1.0},
    "mouthCues": [
        {"start": 0.0, "end": 0.3, "value": "X"},
        {"start": 0.3, "end": 0.6, "value": "A"},
        {"start": 0.6, "end": 1.0, "value": "B"},
    ],
}


def test_parse_rhubarb_keeps_real_timestamps():
    parsed = parse_rhubarb(FIXTURE, source="line.wav")
    assert parsed["schema"] == "ahos.lipsync.rhubarb.v1"
    assert len(parsed["visemes"]) == 3
    assert parsed["visemes"][1] == {"start": 0.3, "end": 0.6, "value": "A"}
    assert parsed["duration"] == 1.0


def test_parse_rejects_empty_or_reversed_cues():
    with pytest.raises(RhubarbError):
        parse_rhubarb({"mouthCues": []})
    bad = {"metadata": {"duration": 1.0}, "mouthCues": [
        {"start": 0.5, "end": 0.4, "value": "A"}]}
    with pytest.raises(RhubarbError):
        parse_rhubarb(bad)


def test_viseme_at_returns_silence_outside_cues():
    cues = parse_rhubarb(FIXTURE)["visemes"]
    assert viseme_at(cues, 0.1) == "X"
    assert viseme_at(cues, 0.4) == "A"
    assert viseme_at(cues, 0.8) == "B"
    assert viseme_at(cues, 2.0) == "X"


def test_load_visemes_reads_file(tmp_path):
    path = tmp_path / "mouth.json"
    path.write_text(json.dumps(FIXTURE), encoding="utf-8")
    assert len(load_visemes(path)["visemes"]) == 3


def test_missing_wav_is_reported_not_faked(tmp_path):
    from ahos.lipsync import generate_visemes

    with pytest.raises(RhubarbError):
        generate_visemes(tmp_path / "missing.wav", tmp_path / "out.json")
