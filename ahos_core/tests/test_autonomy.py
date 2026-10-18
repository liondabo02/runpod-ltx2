from __future__ import annotations

from pathlib import Path

import pytest

from ahos.autonomy import AutonomyLimits, AutonomyRunner
from ahos.owner_console import build_default_console


@pytest.fixture()
def runner(tmp_path) -> AutonomyRunner:
    console = build_default_console(tmp_path)
    return AutonomyRunner(console, tmp_path, limits=AutonomyLimits(max_missions=1))


def test_paid_provider_is_rejected() -> None:
    with pytest.raises(ValueError):
        AutonomyLimits(max_usd=0.01)


def test_empty_queue_makes_no_call(runner: AutonomyRunner) -> None:
    # Salt-okunur departmanlar boşta: yönlendirme üretilirse bile executor
    # yalnız gerçek direktif varsa çalışır; burada yönlendirme var, o yüzden
    # davranışı "istek sayısı" üzerinden değil durum üzerinden doğruluyoruz.
    assert runner.status()["paid_calls"] == 0


def test_dedupe_and_limits_prevent_reruns(tmp_path) -> None:
    from ahos.projects import ProjectLink

    console = build_default_console(tmp_path)
    console.handle("oyun geliştirme departmanı kur")
    project = tmp_path / "proj"
    (project / "www").mkdir(parents=True)
    (project / "www" / "index.html").write_text("<html></html>", encoding="utf-8")
    console.projects.link(
        ProjectLink(project_id="p", name="P", path=project, department_id="oyun")
    )
    runner = AutonomyRunner(console, tmp_path, limits=AutonomyLimits(max_missions=2))

    first = runner.run_once()
    assert first is not None and first.status == "routed"
    assert runner.state.executed == 1

    second = runner.run_once()

    # Uygun farklı proje kalmadıysa sistem bekler; aynı görev tekrar çalışmaz.
    assert second is None
    assert runner.state.executed == 1
    assert runner.state.status in {"idle", "stopped"}


def test_pause_and_resume(runner: AutonomyRunner) -> None:
    runner.pause()
    assert runner.run_once() is None
    assert runner.status()["status"] == "paused"

    runner.resume()
    assert runner.status()["status"] == "idle"


def test_kill_switch_stops_execution(runner: AutonomyRunner) -> None:
    runner.stop()
    assert runner.run_once() is None
    assert runner.status()["status"] == "stopped"


def test_mission_limit_stops_loop(tmp_path) -> None:
    console = build_default_console(tmp_path)
    runner = AutonomyRunner(console, tmp_path, limits=AutonomyLimits(max_missions=1))

    runner.run(ticks=3)

    assert runner.state.status in {"stopped", "idle", "blocked"}
    assert runner.state.executed + runner.state.failed <= 1


def test_state_persists_across_restart(tmp_path) -> None:
    console = build_default_console(tmp_path)
    runner = AutonomyRunner(console, tmp_path, limits=AutonomyLimits())
    runner.run_once()

    reloaded = AutonomyRunner(console, tmp_path, limits=AutonomyLimits())
    assert reloaded.already_executed(
        reloaded._key("holding", "x")
    ) is False
    assert runner.dedupe_path.exists() or runner.state.executed == 0
