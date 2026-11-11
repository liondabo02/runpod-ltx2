"""P12-A: real render backend produces a verified 1080p24 film with audio."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from ahos_studio_dispatcher import dispatch, dispatch_stage  # noqa: E402
from ahos_text_to_cartoon import parse_story  # noqa: E402

JOB = ROOT / "studio" / "jobs" / "p12-render"
FILM = JOB / "render-technical-5s.mp4"
EVIDENCE = json.loads((JOB / "render-evidence.json").read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_render_artifact_is_real_1080p24_with_audio():
    assert FILM.is_file() and FILM.stat().st_size > 100_000
    assert EVIDENCE["stage"] == "render" and EVIDENCE["status"] == "PASSED"
    assert EVIDENCE["cost_eur"] == 0 and EVIDENCE["commercial_license_verified"] is True
    assert EVIDENCE["artifacts"][0]["sha256"] == sha(FILM)
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=codec_type,width,height,r_frame_rate", "-of", "json", str(FILM)],
        capture_output=True, text=True, check=True)
    streams = json.loads(probe.stdout)["streams"]
    video = [s for s in streams if s["codec_type"] == "video"][0]
    assert (video["width"], video["height"]) == (1920, 1080)
    assert video["r_frame_rate"] == "24/1"
    assert any(s["codec_type"] == "audio" for s in streams)


def test_dispatcher_runs_and_verifies_render_stage(tmp_path):
    result = dispatch_stage({"cast": ["aden", "kaan"]}, tmp_path / "job", "render")
    assert result["status"] == "VERIFIED_TECHNICAL"
    assert result["production_ready"] is False
    assert result["stages"][0]["stage"] == "render"
    artifact = tmp_path / "job" / result["stages"][0]["artifacts"][0]["path"]
    assert artifact.is_file()


def test_full_dispatch_still_blocks_at_missing_character_model(tmp_path):
    result = dispatch(parse_story("Aden ve Kaan bahçede", 6), tmp_path / "job")
    assert result["status"] == "BLOCKED"
    assert result["stages"][0]["stage"] == "character_model"
    assert result["production_ready"] is False
