"""Dizi hattı: sezon planı, bölüm sürekliliği, durum dosyası."""

from __future__ import annotations

import json

import pytest

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


def _llm_json(total_seconds: float = 480.0) -> str:
    lines = []
    for index in range(8):
        lines.append({
            "speaker": "aden" if index % 2 == 0 else "kaan",
            "text": f"LLM replik {index + 1}",
            "seconds": total_seconds / 8,
        })
    return json.dumps({"scenes": [{"title": "LLM sahne", "lines": lines}]})


def test_llm_script_is_used_and_duration_is_exact(tmp_path):
    series = _series()
    plan = plan_season(series, episodes=1)[0]
    calls = {"count": 0}

    def fake(prompt, cfg):
        calls["count"] += 1
        return _llm_json(480.0)

    ledger_path = tmp_path / "ledger.json"
    episode = build_episode(
        series, plan, script_adapter=fake,
        cfg={"provider": "llm", "model_ref": "config://llm/model", "budget_usd_cap": 2.0},
        approval=True, target_seconds=480.0, ledger_path=ledger_path,
    )

    assert calls["count"] == 1
    assert episode.script_ledger["script_source"] == "llm"
    assert episode.script_ledger["attempts"] == 1
    assert all(line.text.startswith("LLM replik") for scene in episode.scenes for line in scene.lines)
    assert episode.duration() == pytest.approx(480.0, abs=1e-9)
    assert json.loads(ledger_path.read_text(encoding="utf-8"))["script_source"] == "llm"


def test_invalid_llm_output_retries_once_then_template(tmp_path):
    series = _series()
    plan = plan_season(series, episodes=1)[0]
    calls = {"count": 0}

    def broken(prompt, cfg):
        calls["count"] += 1
        return "not-json"

    ledger_path = tmp_path / "ledger.json"
    episode = build_episode(
        series, plan, script_adapter=broken,
        cfg={"provider": "llm", "budget_usd_cap": 2.0},
        approval=True, target_seconds=480.0, ledger_path=ledger_path,
    )

    assert calls["count"] == 2
    assert episode.script_ledger["script_source"] == "template"
    assert episode.script_ledger["failure_class"] == "invalid_output"
    assert episode.duration() == pytest.approx(480.0, abs=1e-9)


def test_paid_adapter_is_not_called_without_approval(tmp_path):
    series = _series()
    plan = plan_season(series, episodes=1)[0]
    calls = {"count": 0}

    def fake(prompt, cfg):
        calls["count"] += 1
        return _llm_json()

    ledger_path = tmp_path / "ledger.json"
    episode = build_episode(
        series, plan, script_adapter=fake,
        cfg={"provider": "llm", "budget_usd_cap": 2.0},
        approval=False, target_seconds=480.0, ledger_path=ledger_path,
    )

    assert calls["count"] == 0
    assert episode.script_ledger["blocked_budget"] is True
    assert episode.script_ledger["script_source"] == "template"


@pytest.mark.parametrize("target", [480.0, 540.0, 600.0])
def test_template_fallback_has_exact_target_duration(target):
    series = _series()
    plan = plan_season(series, episodes=1)[0]
    episode = build_episode(series, plan, target_seconds=target)
    assert episode.duration() == pytest.approx(target, abs=1e-9)
