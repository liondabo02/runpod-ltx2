"""Objective CPU video quality tests; mock signals never certify actual film."""
import importlib.util
import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("studio_media_objective_qa",ROOT/"tools/studio_media_objective_qa.py")
qa=importlib.util.module_from_spec(spec)
spec.loader.exec_module(qa)


def media_meta(*,fps="24/1",seconds="4.0",has_audio=True):
    streams=[{"codec_type":"video","width":1280,"height":720,
              "avg_frame_rate":fps}]
    if has_audio:streams.append({"codec_type":"audio"})
    return {"streams":streams,"format":{"duration":seconds}}


def fake_media(tmp_path, monkeypatch, logs="", meta=None):
    source=tmp_path/"media-test.mp4"
    source.write_bytes(b"simulated media bytes for transport testing"*5000)
    monkeypatch.setattr(qa,"_probe",lambda *_:meta or media_meta())
    monkeypatch.setattr(qa.shutil,"which",lambda *_:"/usr/bin/ffmpeg")
    monkeypatch.setattr(qa.subprocess,"run",lambda *a,**k:
                        SimpleNamespace(returncode=0,stderr=logs))
    return source


def test_neutral_signals_pass_technical_but_not_creative(tmp_path,monkeypatch):
    source=fake_media(tmp_path,monkeypatch)
    result=qa.assess(source,dialogue=True)
    assert result["objective_technical_status"]=="PASSED"
    assert result["creative_quality_verified"] is False
    assert result["actor_identity_verified"] is False
    assert result["production_ready"] is False


def test_freeze_excess_detected(tmp_path,monkeypatch):
    logs=("lavfi.freezedetect.freeze_start: 0.0\n"
          "lavfi.freezedetect.freeze_end: 2.4 | lavfi.freezedetect.freeze_duration: 2.4")
    source=fake_media(tmp_path,monkeypatch,logs=logs)
    result=qa.assess(source)
    assert result["frozen_seconds"]==2.4
    assert "EXCESSIVE_FROZEN_FRAMES" in result["failures"]


def test_black_video_and_silent_dialogue_detected(tmp_path,monkeypatch):
    logs=("black_start:0 black_end:2.9 black_duration:2.9\n"
          "silence_start: 0\nsilence_end: 3.1 | silence_duration: 3.1")
    source=fake_media(tmp_path,monkeypatch,logs=logs)
    result=qa.assess(source,dialogue=True)
    assert set(result["failures"])=={
        "EXCESSIVE_BLACK_FRAMES","EXCESSIVE_DIALOGUE_SILENCE"}


def test_audio_absent_is_blocked(tmp_path,monkeypatch):
    source=fake_media(tmp_path,monkeypatch,meta=media_meta(has_audio=False))
    with pytest.raises(qa.TechnicalMediaError,match="audio AND video"):
        qa.assess(source)


def test_frame_rate_and_duration_limits(tmp_path,monkeypatch):
    source=fake_media(tmp_path,monkeypatch,meta=media_meta(fps="30/1"))
    with pytest.raises(qa.TechnicalMediaError,match="frame rate"):
        qa.assess(source)
    monkeypatch.setattr(qa,"_probe",lambda _:media_meta(seconds="200.0"))
    with pytest.raises(qa.TechnicalMediaError,match="unbounded"):
        qa.assess(source)


def test_overlap_union_and_open_ended_ranges():
    assert qa._total([(0,2),(1.5,3)])==3
    r=qa._ranges("silence_start: 1.0\n","silence_start","silence_end",
                 "silence_duration",3.0)
    assert r==[(1.0,3.0)]


def test_actual_ffmpeg_decoding_short_moving_and_audible_clip(tmp_path):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("ffmpeg/ffprobe absent on this CI runner")
    target=tmp_path/"real-technical-fixture.mp4"
    cmd=[
        "ffmpeg","-v","error","-y",
        "-f","lavfi","-i","testsrc2=size=640x360:rate=24:duration=3",
        "-f","lavfi","-i","sine=frequency=440:sample_rate=44100:duration=3",
        "-c:v","mpeg4","-q:v","2","-r","24","-c:a","aac",
        "-shortest",str(target),
    ]
    subprocess.run(cmd,capture_output=True,check=True,timeout=45)
    assert target.stat().st_size>100000
    result=qa.assess(target,min_width=640,min_height=360,dialogue=False)
    assert result["objective_technical_status"]=="PASSED"
    assert result["fps"]==24
    assert result["actor_identity_verified"] is False
