from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from ahos.autoschedule import AutoLimits, BoundedScheduler


class FakeRunner:
    def __init__(self, results: list[object]) -> None:
        self.results = results
        self.calls = 0

    def run_once(self):
        self.calls += 1
        if not self.results:
            return None
        return self.results.pop(0)


def _outcome(mission_id: str, status: str = "routed"):
    return SimpleNamespace(mission=SimpleNamespace(mission_id=mission_id), status=status)


def _clock(hour: int):
    return lambda: datetime(2026, 10, 18, hour, 0, tzinfo=timezone.utc)


def test_paid_budget_must_be_zero() -> None:
    with pytest.raises(ValueError):
        AutoLimits(max_usd_per_hour=1.0)


def test_hourly_quota_stops_further_missions(tmp_path) -> None:
    runner = FakeRunner([_outcome(f"m-{i}") for i in range(5)])
    scheduler = BoundedScheduler(
        runner,
        tmp_path,
        limits=AutoLimits(max_missions_per_hour=2, max_missions_total=10),
        wall_clock=_clock(10),
        sleep=lambda seconds: None,
    )

    first = scheduler.tick()
    second = scheduler.tick()
    third = scheduler.tick()

    assert [first, second, third] == ["running", "running", "quota_wait"]
    assert runner.calls == 2


def test_new_hour_resets_quota(tmp_path) -> None:
    runner = FakeRunner([_outcome("m-1"), _outcome("m-2")])
    hours = iter([10, 10, 11])
    scheduler = BoundedScheduler(
        runner,
        tmp_path,
        limits=AutoLimits(max_missions_per_hour=1, max_missions_total=5),
        wall_clock=lambda: datetime(2026, 10, 18, next(hours), 0, tzinfo=timezone.utc),
        sleep=lambda seconds: None,
    )

    assert scheduler.tick() == "running"
    assert scheduler.tick() == "quota_wait"
    assert scheduler.tick() == "running"
    assert scheduler.state.missions_total == 2


def test_idle_queue_does_not_call_runner_again(tmp_path) -> None:
    runner = FakeRunner([])
    sleeps: list[float] = []
    scheduler = BoundedScheduler(
        runner,
        tmp_path,
        limits=AutoLimits(idle_sleep_seconds=7),
        wall_clock=_clock(9),
        sleep=sleeps.append,
    )

    outcomes = scheduler.run(max_ticks=5)

    assert outcomes == ["idle"]
    assert runner.calls == 1
    assert sleeps == [7]


def test_session_limit_stops_scheduler(tmp_path) -> None:
    runner = FakeRunner([_outcome(f"m-{i}") for i in range(5)])
    scheduler = BoundedScheduler(
        runner,
        tmp_path,
        limits=AutoLimits(max_missions_per_hour=10, max_missions_total=1),
        wall_clock=_clock(12),
        sleep=lambda seconds: None,
    )

    assert scheduler.tick() == "running"
    assert scheduler.tick() == "stopped"
    assert runner.calls == 1


def test_kill_switch_and_pause_block_execution(tmp_path) -> None:
    runner = FakeRunner([_outcome("m-1")])
    scheduler = BoundedScheduler(runner, tmp_path, wall_clock=_clock(8))

    (tmp_path / "autonomy.pause").write_text("x", encoding="utf-8")
    assert scheduler.tick() == "paused"
    (tmp_path / "autonomy.pause").unlink()

    (tmp_path / "autonomy.stop").write_text("x", encoding="utf-8")
    assert scheduler.tick() == "stopped"
    assert runner.calls == 0


def test_state_survives_restart(tmp_path) -> None:
    runner = FakeRunner([_outcome("m-1"), _outcome("m-2")])
    scheduler = BoundedScheduler(
        runner,
        tmp_path,
        limits=AutoLimits(max_missions_per_hour=5, max_missions_total=5),
        wall_clock=_clock(14),
        sleep=lambda seconds: None,
    )
    scheduler.tick()

    reloaded = BoundedScheduler(runner, tmp_path, wall_clock=_clock(14))
    assert reloaded.state.missions_total == 1
    assert reloaded.state.hour_key == "2026-10-18T14"
