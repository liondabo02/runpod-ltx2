"""Sahne araçları — LTX Space isteği ve teslim paketi (ağ çağrısı olmadan)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS))


def _moving_video(path: Path, frames: int = 24, width: int = 640, height: int = 360) -> Path:
    from PIL import Image, ImageDraw

    process = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{width}x{height}", "-r", "24", "-i", "-",
         "-pix_fmt", "yuv420p", str(path)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    for index in range(frames):
        image = Image.new("RGB", (width, height), (46, 94, 52))
        draw = ImageDraw.Draw(image)
        x = (index * 18) % (width - 90)
        draw.rectangle([x, 140, x + 90, 230], fill=(250, 220, 120))
        process.stdin.write(image.tobytes())
    process.stdin.close()
    process.wait(timeout=60)
    assert process.returncode == 0
    return path


def test_quota_error_is_classified():
    import ltx_space_render

    assert ltx_space_render.classify_error(
        "You have exceeded your ZeroGPU runs limit.") == "zerogpu_quota"
    assert ltx_space_render.classify_error(
        "Value 6.0 is greater than maximum value 5.0.") == "invalid_parameter"
    assert ltx_space_render.classify_error("boom") == "provider_error"


def test_prompts_come_from_scene_canon():
    import ltx_space_render

    keyframe = ltx_space_render.build_keyframe_prompt()
    baby = ltx_space_render.build_keyframe_prompt(variant="baby")
    video = ltx_space_render.build_video_prompt()
    for text in (keyframe, baby, video):
        assert "Aden" in text and "Kaan" in text
        assert "kite" in text.lower()
    assert "TODDLER" in baby and "three quarters" in baby
    assert baby != keyframe


def test_space_duration_cap_is_enforced_before_network(tmp_path):
    import ltx_space_render

    with pytest.raises(ValueError):
        ltx_space_render.generate_video(
            keyframe=tmp_path / "k.png", seed=1, duration=6.0,
            width=1280, height=720, decoder="diffusion",
            out_dir=tmp_path, tag="x")


def test_finalize_scene_writes_package_and_never_marks_creative_pass(tmp_path):
    import finalize_scene

    raw = _moving_video(tmp_path / "raw.mp4")
    out = tmp_path / "pkg"
    manifest = finalize_scene.finalize(
        raw, out, tag="t1", seconds=1.0, width=960, height=540, fps=24,
        model="test-model", cost_usd=0.0, workflow="test-workflow")

    assert Path(manifest["files"]["video"]["path"]).is_file()
    assert Path(manifest["files"]["start_frame"]["path"]).is_file()
    assert Path(manifest["files"]["end_frame"]["path"]).is_file()
    assert (out / "qa-technical.json").is_file()
    assert (out / "KALITE-RAPORU.md").is_file()
    assert manifest["creative"]["status"] == "NOT_EVALUATED"
    assert manifest["creative"]["approver"] == "Harun"
    assert manifest["technical"]["video"]["width"] == 960
    assert abs(manifest["technical"]["duration_seconds"] - 1.0) < 0.2

    qa = json.loads((out / "qa-technical.json").read_text(encoding="utf-8"))
    assert qa["motion"]["freeze_verdict"] == "PASS"
    assert qa["creative"]["status"] == "NOT_EVALUATED"


def test_finalize_scene_rejects_missing_input(tmp_path):
    import finalize_scene

    with pytest.raises(FileNotFoundError):
        finalize_scene.finalize(tmp_path / "yok.mp4", tmp_path / "out",
                                tag="x", seconds=1.0, width=960, height=540,
                                fps=24, model="m", cost_usd=0.0)
