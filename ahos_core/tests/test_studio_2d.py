"""Çizgi film hattı: gerçek video üretimi ve bağımsız teslim denetimi."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from ahos.studio_2d import Episode, Line, Scene, render_episode
from ahos.studio_qa import verify_episode


def _episode(seconds: float = 1.0, scenes: int = 2) -> Episode:
    items = []
    for index in range(scenes):
        items.append(
            Scene(
                scene_id=f"s{index + 1}",
                setting=f"sahne {index + 1}",
                background=("day", "sunset", "night")[index % 3],
                characters=["aden", "kaan"],
                lines=[Line(f"s{index + 1}", "aden", f"replik {index + 1}", seconds)],
            )
        )
    return Episode(title="test", scenes=items)


def test_render_produces_a_playable_video(tmp_path):
    manifest = render_episode(_episode(seconds=1.0, scenes=1), tmp_path)

    video = Path(manifest["video"])
    assert video.is_file() and video.stat().st_size > 10_000
    assert manifest["scenes"] == 1
    assert abs(manifest["duration_seconds"] - 1.0) < 0.01

    report = verify_episode(video, expected_scenes=1, expected_duration=1.0)
    assert report["passed"] is True, report
    assert report["measurements"]["video_streams"] == 1
    assert report["measurements"]["resolution"] == [1280, 720]


def test_gate_rejects_a_static_slideshow(tmp_path):
    """Hareket yoksa teslim reddedilir: slayt video çizgi film sayılmaz."""

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        pytest.skip("ffmpeg yok")

    frame = tmp_path / "still.png"
    from PIL import Image

    Image.new("RGB", (640, 360), (40, 90, 160)).save(frame)

    video = tmp_path / "slideshow.mp4"
    subprocess.run(
        [ffmpeg, "-y", "-loglevel", "error", "-loop", "1", "-t", "2", "-i", str(frame),
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video)],
        capture_output=True, text=True, check=True, timeout=120,
    )

    report = verify_episode(video, expected_scenes=1, expected_duration=2.0)
    assert report["passed"] is False
    assert any("hareketsiz" in problem for problem in report["problems"]), report


def test_gate_flags_missing_audio_as_a_note_not_a_pass(tmp_path):
    manifest = render_episode(_episode(seconds=1.0, scenes=1), tmp_path)
    report = verify_episode(Path(manifest["video"]), expected_scenes=1, expects_audio=False)
    assert report["passed"] is True
    assert report["score"] < 100
    assert any("ses yok" in note for note in report["notes"])

    audio_report = verify_episode(Path(manifest["video"]), expected_scenes=1, expects_audio=True)
    assert audio_report["passed"] is False
    assert any("ses akışı" in problem for problem in audio_report["problems"])


def test_episode_manifest_is_written(tmp_path):
    manifest = render_episode(_episode(seconds=1.0, scenes=1), tmp_path)
    stored = json.loads((tmp_path / "episode.json").read_text(encoding="utf-8"))
    assert stored["title"] == manifest["title"]
    assert stored["frames"] == manifest["frames"]
