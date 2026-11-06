"""Dizi hattı: sezon planı, bölüm sürekliliği, durum dosyası."""

from __future__ import annotations

import json

from ahos.series import (
    Character,
    SeriesBible,
    build_episode,
    load_state,
    plan_season,
    save_state,
)
from ahos.series_cli import main as series_main


def _series() -> SeriesBible:
    return SeriesBible(
        series_id="test", title="Aden ve Kaan", premise="İki kardeş keşfe çıkar.",
        characters=[Character("aden", "Aden", "female"), Character("kaan", "Kaan", "male")],
    )


def test_plan_season_returns_requested_length():
    plans = plan_season(_series(), episodes=50)
    assert len(plans) == 50
    assert [plan.number for plan in plans] == list(range(1, 51))
    assert all(plan.cliffhanger for plan in plans)
    assert plans[0].title.startswith("Yeni bir şey")


def test_episode_carries_the_cliffhanger_and_a_fixed_cast():
    series = _series()
    plan = plan_season(series, episodes=10)[0]
    episode = build_episode(series, plan, lines_per_scene=2, line_seconds=2.0)

    assert episode.title.endswith("B1")
    assert len(episode.scenes) == 4
    last_line = episode.scenes[-1].lines[-1]
    assert last_line.text == plan.cliffhanger
    for scene in episode.scenes:
        assert scene.characters == ["aden", "kaan"]


def test_state_roundtrip(tmp_path):
    state = {"produced": [1, 2], "next_episode": 3, "planned": 50}
    save_state(tmp_path, state)
    assert load_state(tmp_path) == state
    assert json.loads((tmp_path / "series-state.json").read_text(encoding="utf-8"))["next_episode"] == 3


def test_cli_plan_writes_season_file(tmp_path):
    code = series_main(["--root", str(tmp_path), "plan", "--episodes", "12"])
    assert code == 0
    season = json.loads((tmp_path / "season.json").read_text(encoding="utf-8"))
    assert len(season) == 12
    assert (tmp_path / "series.json").is_file()
