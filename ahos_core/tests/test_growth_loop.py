from __future__ import annotations

from ahos.growth_loop import GROWTH_CYCLE, GrowthLoop
from ahos.owner_console import build_default_console


def test_growth_loop_runs_one_mission_per_tick(tmp_path) -> None:
    console = build_default_console(tmp_path)
    console.handle("çizgi film departmanı kur")
    loop = GrowthLoop(console, interval_seconds=60, missions_per_tick=1)

    ticks = loop.run_once()

    assert len(ticks) == 1
    tick = ticks[0]
    assert tick.department_id
    assert tick.status in {"routed", "blocked"}
    assert tick.mission_id and tick.mission_id.startswith("CMD-")
    assert loop.history == ticks

    missions = console.queue.list()
    assert any(m.mission_id == tick.mission_id for m in missions)


def test_growth_loop_rotates_objectives_per_department(tmp_path) -> None:
    console = build_default_console(tmp_path)
    loop = GrowthLoop(console, interval_seconds=60)
    spec = console.book.require("creative")

    first = loop.next_objective(spec)
    loop.console.run_department_mission(spec, first)
    second = loop.next_objective(spec)

    assert first != second
    assert second in GROWTH_CYCLE


def test_growth_loop_prefers_departments_with_fewer_missions(tmp_path) -> None:
    console = build_default_console(tmp_path)
    software = console.book.require("software")
    for _ in range(3):
        console.run_department_mission(software, "küçük bir görev")

    loop = GrowthLoop(console, interval_seconds=60)
    planned = loop.plan_tick()

    assert planned
    assert planned[0][0].department_id != "software"


def test_growth_loop_stops_when_stop_file_exists(tmp_path) -> None:
    console = build_default_console(tmp_path)
    stop_file = tmp_path / "growth-loop.stop"
    stop_file.write_text("stop", encoding="utf-8")
    loop = GrowthLoop(console, interval_seconds=60, stop_file=stop_file)

    loop.run(max_ticks=2)
    assert loop.history == []

    stop_file.unlink()
    loop.run(max_ticks=1, sleeper=lambda _seconds: None)
    assert len(loop.history) == 1


def test_growth_loop_can_be_limited_to_named_departments(tmp_path) -> None:
    console = build_default_console(tmp_path)
    loop = GrowthLoop(
        console,
        interval_seconds=60,
        only_departments=("quality",),
    )

    planned = loop.plan_tick()

    assert len(planned) == 1
    assert planned[0][0].department_id == "quality"


def test_growth_status_reports_last_tick(tmp_path) -> None:
    console = build_default_console(tmp_path)
    loop = GrowthLoop(console, interval_seconds=30, missions_per_tick=2)
    loop.run_once()

    status = loop.status()

    assert status["interval_seconds"] == 30
    assert status["missions_per_tick"] == 2
    assert status["ticks"] == 2
    assert status["last"] is not None

def test_panel_can_start_and_stop_the_growth_loop(tmp_path) -> None:
    from ahos.control_center import ControlCenterState

    state = ControlCenterState(tmp_path)
    message = state.start_growth_loop(interval_seconds=1, missions_per_tick=1)
    assert "başladı" in message

    state.stop_growth_loop()
    assert state.growth_status()["running"] is False
    assert (tmp_path / "growth-loop.stop").exists()
