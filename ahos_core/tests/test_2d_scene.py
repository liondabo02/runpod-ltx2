"""2D iskelet sahnesi: gerçek MP4 var, 3D/profesyonel iddiası yok."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "deliverables" / "S01E001-SCENE01-2D-RIG"
VIDEO = DIR / "S01E001-SCENE01-2D-RIG-1080p24.mp4"
MANIFEST = json.loads((DIR / "scene-manifest.json").read_text(encoding="utf-8"))
QA = json.loads((DIR / "qa.json").read_text(encoding="utf-8"))
sys.path.insert(0, str(ROOT / "tools"))

import identity_lock  # noqa: E402
import studio_production_gate as gate  # noqa: E402


def test_video_is_real_1080p24_twelve_seconds_silent():
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(VIDEO)],
        capture_output=True, text=True, check=True)
    meta = json.loads(probe.stdout)
    video = next(s for s in meta["streams"] if s["codec_type"] == "video")
    assert video["codec_name"] == "h264"
    assert (video["width"], video["height"]) == (1920, 1080)
    assert video["r_frame_rate"] == "24/1" and video["nb_frames"] == "288"
    assert abs(float(meta["format"]["duration"]) - 12.0) < 0.05
    assert not any(s["codec_type"] == "audio" for s in meta["streams"])
    assert hashlib.sha256(VIDEO.read_bytes()).hexdigest() == MANIFEST["sha256"] == QA["sha256"]


def test_manifest_declares_2d_joints_and_no_professional_claim():
    assert MANIFEST["is_3d"] is False
    assert MANIFEST["status"] == "TECHNICAL_TEST_PENDING_REVIEW"
    assert MANIFEST["professional_quality"] == "NOT_ACHIEVED"
    assert MANIFEST["audio"] == "SILENT"
    assert {"hip", "knee", "ankle", "shoulder", "elbow", "hand", "head", "eyes", "mouth"} <= set(MANIFEST["joints"])


def test_qa_shows_motion_and_no_blank_video():
    assert QA["status"] == "TECHNICAL_TEST_PENDING_REVIEW"
    assert QA["blank_frames"] == 0
    assert QA["mean_motion"] > 0.2
    assert QA["is_3d"] is False


def test_evidence_keyframes_exist():
    for name in ("frame-0000.png", "frame-0144.png", "frame-0287.png"):
        assert (DIR / "evidence" / name).is_file()


def test_storyboard_gate_passes_but_professional_gate_fails():
    assert gate.assess(ROOT, level="storyboard")["pass"] is True
    assert gate.assess(ROOT, level="professional")["pass"] is False


def test_identity_lock_still_valid():
    assert identity_lock.verify() == []
    assert "APPROVED" not in json.dumps(MANIFEST)
