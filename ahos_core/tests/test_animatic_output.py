"""P4 animatik çıktısı: gerçek MP4, sessiz, 30 sn, 1080p24."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "deliverables" / "S01E001-OPEN-30s-ANIMATIC"
VIDEO = DIR / "S01E001-OPEN-30s-ANIMATIC-1080p24.mp4"
MANIFEST = json.loads((DIR / "animatic-manifest.json").read_text(encoding="utf-8"))
QA = json.loads((DIR / "qa.json").read_text(encoding="utf-8"))


def test_video_exists_and_matches_manifest():
    assert VIDEO.is_file()
    assert VIDEO.stat().st_size == MANIFEST["bytes"] > 500_000
    assert hashlib.sha256(VIDEO.read_bytes()).hexdigest() == MANIFEST["sha256"]
    assert MANIFEST["status"] == "VIDEO_READY"


def test_ffprobe_reports_1080p24_30_seconds_silent():
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(VIDEO)],
        capture_output=True, text=True, check=True)
    meta = json.loads(probe.stdout)
    video = next(stream for stream in meta["streams"] if stream["codec_type"] == "video")
    assert video["codec_name"] == "h264"
    assert video["width"] == 1920 and video["height"] == 1080
    assert video["r_frame_rate"] == "24/1"
    assert video["nb_frames"] == "720"
    assert abs(float(meta["format"]["duration"]) - 30.0) < 0.05
    assert not any(stream["codec_type"] == "audio" for stream in meta["streams"])


def test_qa_has_no_black_video_and_only_transition_blanks():
    assert QA["status"] == "VIDEO_READY"
    assert QA["blank_frames"] == 12
    assert QA["frames"] == 720 and QA["content_frames"] == 708
    assert all(0.0 <= t <= 25.2 for t in QA["blank_timestamps"])


def test_source_props_have_six_text_cards_and_no_characters():
    props = json.loads((ROOT / "studio" / "integration" / "openmontage-props"
                        / "s01e001-opening-storyboard.json").read_text(encoding="utf-8"))
    assert len(props["cuts"]) == 6
    assert all(cut["type"] == "text_card" and cut["source"] == "" for cut in props["cuts"])
    assert props["status"] == "PLACEHOLDER_NOT_APPROVED"


def test_cost_guard_is_still_wired_and_enabled_by_default():
    source = (ROOT / "ahos_core" / "ahos" / "llm_executor.py").read_text(encoding="utf-8")
    assert 'AHOS_STUDIO_COST_GUARD", "1"' in source
    assert "_studio_budget_preflight(system_prompt" in source
