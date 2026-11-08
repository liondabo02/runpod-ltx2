"""Çizgi film hattı: brief → bölüm → kapı; sahip komutundan üretim."""

from __future__ import annotations

import json
from pathlib import Path

from ahos.owner_cli import main as owner_main
from ahos.studio_pipeline import produce_episode, storyboard


def test_storyboard_is_deterministic():
    first = storyboard("parkta bir gün", scenes=3, seconds=2.0)
    second = storyboard("parkta bir gün", scenes=3, seconds=2.0)

    assert [s.scene_id for s in first.scenes] == [s.scene_id for s in second.scenes]
    assert first.title == second.title
    assert abs(first.duration() - second.duration()) < 1e-9
    assert len(first.scenes) == 3
    assert all(scene.lines for scene in first.scenes)


def test_produce_episode_without_voice_passes_the_gate(tmp_path):
    episode = storyboard("deneme", scenes=1, seconds=2.0)
    report = produce_episode(episode, tmp_path, use_voice=False)

    assert report["passed"] is True, report
    assert (tmp_path / "episode.mp4").is_file()
    assert (tmp_path / "episode.srt").is_file()
    assert (tmp_path / "brief.json").is_file()
    assert (tmp_path / "story.json").is_file()

    stored = json.loads((tmp_path / "acceptance.json").read_text(encoding="utf-8"))
    assert stored["passed"] is True
    assert stored["voice"] is None


def test_owner_command_produces_an_episode(tmp_path):
    code = owner_main([
        "--runtime-dir", str(tmp_path / "runtime"),
        "--scenes", "1", "--seconds", "1", "--no-voice",
        "çizgi film: kısa bir test",
    ])

    assert code == 0
    episodes = list((tmp_path / "runtime" / "studio-episodes").glob("*/episode.mp4"))
    assert len(episodes) == 1
    acceptance = json.loads(episodes[0].with_name("acceptance.json").read_text(encoding="utf-8"))
    assert acceptance["passed"] is True
