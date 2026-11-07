"""tools/creative_qa.py — teknik ölçüm ile yaratıcı onayı ayırır."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS))


def _moving_video(path: Path, frames: int = 24, width: int = 640, height: int = 360) -> Path:
    """Hareketli bir kare dizisi üretir (gerçek piksel hareketi, renk değişimi değil)."""

    from PIL import Image, ImageDraw

    process = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{width}x{height}", "-r", "24", "-i", "-",
         "-pix_fmt", "yuv420p", str(path)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    for index in range(frames):
        image = Image.new("RGB", (width, height), (51, 102, 153))
        draw = ImageDraw.Draw(image)
        x = (index * 18) % (width - 90)
        draw.rectangle([x, 140, x + 90, 230], fill=(250, 250, 250))
        process.stdin.write(image.tobytes())
    process.stdin.close()
    process.wait(timeout=60)
    assert process.returncode == 0
    return path


def _static_video(path: Path, width: int = 640, height: int = 360) -> Path:
    done = subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
         "-i", f"color=c=0x336699:size={width}x{height}:rate=24",
         "-t", "1", "-pix_fmt", "yuv420p", str(path)],
        capture_output=True, timeout=60,
    )
    assert done.returncode == 0, done.stderr[:300]
    return path


def test_moving_video_passes_technical_gates(tmp_path):
    import creative_qa

    video = _moving_video(tmp_path / "moving.mp4")
    report = creative_qa.evaluate(video, scene_id="TEST")
    assert report["technical"]["ok"] is True
    assert report["technical"]["video"]["width"] == 640
    assert report["motion"]["frames_scanned"] >= 20
    assert report["motion"]["changed_pixel_ratio_mean"] > 0.01
    assert report["motion"]["freeze_verdict"] == "PASS"
    # Yaratıcı katman asla otomatik PASS olmaz.
    assert report["creative"]["status"] == "NOT_EVALUATED"
    assert report["creative"]["approver"] == "Harun"


def test_static_video_is_flagged_as_frozen(tmp_path):
    import creative_qa

    report = creative_qa.evaluate(_static_video(tmp_path / "static.mp4"))
    assert report["motion"]["freeze_verdict"] == "FAIL"
    assert report["motion"]["freeze_ratio"] > 0.9


def test_missing_file_is_not_silently_passed(tmp_path):
    import creative_qa

    with pytest.raises(FileNotFoundError):
        creative_qa.evaluate(tmp_path / "yok.mp4")
