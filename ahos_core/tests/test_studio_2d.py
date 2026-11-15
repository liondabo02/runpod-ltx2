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


def _character_frame(name, *, x=640, base=700, t=1.0):
    """Beyaz zemin üzerinde tek karakter karesi (çizim yolu, ffmpeg yok)."""

    from PIL import Image, ImageDraw

    from ahos import studio_2d

    image = Image.new("RGB", (studio_2d.WIDTH, studio_2d.HEIGHT), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    studio_2d._character(draw, name, x, base, t=t, talking=True, gesture=0.6, mouth=0.5)
    return image


def _luma(pixel):
    return 0.2126 * pixel[0] + 0.7152 * pixel[1] + 0.0722 * pixel[2]


def test_character_has_bold_outline():
    """Kontur kuralı: karakter çevresinde OUTLINE rengi belirgin olmalı."""

    from ahos import studio_2d

    image = _character_frame("aden")
    pixels = image.load()
    outline_hits = 0
    sampled = 0
    # baş bölgesinin yatay taramaları (üst/orta/alt)
    for y in range(430, 640, 10):
        for x in range(560, 720, 2):
            sampled += 1
            if pixels[x, y] == studio_2d.OUTLINE:
                outline_hits += 1
    assert sampled > 0
    assert outline_hits > 150, f"kontur pikseli çok az: {outline_hits}"
    assert outline_hits / sampled > 0.05


def test_character_contrasts_with_background():
    """Kontrast kuralı: karakter ile arka plan arasında ΔL >= 25 olmalı."""

    image = _character_frame("kaan")
    pixels = image.load()
    background = _luma(pixels[10, 10])
    samples = [_luma(pixels[x, y]) for y in range(420, 640, 20) for x in range(600, 690, 10)]
    foreground = sum(samples) / len(samples)
    assert abs(foreground - background) >= 25, f"ΔL düşük: {abs(foreground - background):.1f}"


def test_names_produce_distinct_silhouettes():
    """Silüet kuralı: farklı isimler farklı saç kütlesi üretmeli (ayırt edilebilir)."""

    from ahos import studio_2d

    counts = {}
    for name in ("aden", "kaan", "anne"):
        image = _character_frame(name)
        hair = studio_2d.PALETTE[name]["hair"]
        pixels = image.load()
        counts[name] = sum(1 for y in range(400, 520, 2)
                           for x in range(560, 720, 2) if pixels[x, y] == hair)
    assert min(counts.values()) > 0, counts
    assert max(counts.values()) != min(counts.values()), f"siluetler aynı: {counts}"


def test_scene_transition_has_white_flash_frame():
    """Geçiş: sahne başında 1 kare beyaz flash olmalı, sonrasında olmamalı."""

    from ahos import studio_2d

    assert studio_2d._flash_alpha(0.0) == 1.0
    assert studio_2d._flash_alpha(0.5 / studio_2d.FPS) == 1.0
    assert studio_2d._flash_alpha(2.0 / studio_2d.FPS) == 0.0


def test_mouth_has_exactly_three_openness_levels():
    """CN snap: ağız sürekli değil, yalnız 3 kademe (kapalı/yarım/tam) olmalı."""

    from PIL import Image, ImageDraw

    from ahos import studio_2d

    mouth_color = (150, 46, 46)

    def mouth_height(level: float) -> int:
        image = Image.new("RGB", (studio_2d.WIDTH, studio_2d.HEIGHT), (255, 255, 255))
        draw = ImageDraw.Draw(image)
        studio_2d._character(draw, "aden", 640, 700, t=1.0, talking=True, gesture=0.4,
                             mouth=level)
        pixels = image.load()
        rows = [y for y in range(520, 640)
                if any(pixels[x, y] == mouth_color for x in range(600, 680, 2))]
        return max(rows) - min(rows) if rows else 0

    heights = {mouth_height(level) for level in (0.0, 0.1, 0.4, 0.55, 0.8, 1.0)}
    assert len(heights) == 3, f"3 kademe bekleniyordu, bulunan: {sorted(heights)}"


def test_frames_are_not_static_across_time():
    """Statiklik yasağı: farklı zamanlarda üretilen kareler birebir aynı olmamalı."""

    first = _character_frame("aden", t=0.0)
    second = _character_frame("aden", t=0.45)
    assert list(first.getdata()) != list(second.getdata())

    """Statiklik yasağı: farklı zamanlarda üretilen kareler birebir aynı olmamalı."""

    first = _character_frame("aden", t=0.0)
    second = _character_frame("aden", t=0.45)
    assert list(first.getdata()) != list(second.getdata())

