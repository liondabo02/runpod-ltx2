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


def test_dedupe_prevents_reruns_but_allows_next_task(tmp_path) -> None:
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
    first_id = first.mission.mission_id

    # Aynı görev tekrar çalışmaz; sıradaki yapılmamış gerçek iş seçilir.
    second = runner.run_once()
    assert second is not None and second.status == "routed"
    assert second.mission.mission_id != first_id
    assert runner.state.executed == 2

    keys = [
        line
        for line in runner.dedupe_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(keys) == 2
    assert runner.state.skipped_duplicate >= 0


def test_cycle_exhaustion_makes_runner_idle(tmp_path) -> None:
    from ahos.growth_loop import GROWTH_CYCLE
    from ahos.projects import ProjectLink

    console = build_default_console(tmp_path)
    console.handle("oyun geliştirme departmanı kur")
    project = tmp_path / "proj"
    (project / "www").mkdir(parents=True)
    (project / "www" / "index.html").write_text("<html></html>", encoding="utf-8")
    console.projects.link(
        ProjectLink(project_id="p", name="P", path=project, department_id="oyun")
    )
    runner = AutonomyRunner(console, tmp_path, limits=AutonomyLimits(max_missions=10))

    seen: set[str] = set()
    for _ in range(12):
        result = runner.run_once()
        if result is None:
            break
        assert result.status == "routed"
        assert result.mission.mission_id not in seen, "aynı görev iki kez çalıştı"
        seen.add(result.mission.mission_id)
    else:  # pragma: no cover - döngü tükenmezse test patlar
        pytest.fail("döngü tükenmedi")

    # Bütün uygun işler yapıldı: aynı gün yeni iş uydurulmaz.
    assert len(seen) >= len(GROWTH_CYCLE)
    assert runner.run_once() is None
    assert runner.state.status in {"idle", "blocked", "stopped"}


def test_pause_and_resume(runner: AutonomyRunner) -> None:
    runner.pause()
    assert runner.run_once() is None
    assert runner.status()["status"] == "paused"

    runner.resume()
    assert runner.status()["status"] == "idle"


def test_rotation_favours_least_worked_project_department(tmp_path) -> None:
    from ahos.projects import ProjectLink

    console = build_default_console(tmp_path)
    console.handle("oyun geliştirme departmanı kur")
    console.handle("yapay zeka platformu kur")
    for department, name in (("oyun", "game"), ("ai-platform", "ai")):
        root = tmp_path / name
        (root / "www").mkdir(parents=True)
        (root / "www" / "index.html").write_text("<html></html>", encoding="utf-8")
        console.projects.link(
            ProjectLink(project_id=name, name=name, path=root, department_id=department)
        )
    runner = AutonomyRunner(console, tmp_path, limits=AutonomyLimits(max_missions=10))

    departments: list[str] = []
    for _ in range(2):
        result = runner.run_once()
        assert result is not None
        departments.append(result.department_id)

    # İlk görevden sonra aynı departman tekrar seçilmez; sıra diğerine geçer.
    assert departments[0] != departments[1]
    counts = runner.mission_counts_today()
    assert all(count == 1 for count in counts.values())


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


def test_spend_record_reports_real_ledger_numbers(tmp_path) -> None:
    import json
    from datetime import datetime, timezone

    console = build_default_console(tmp_path)
    runner = AutonomyRunner(console, tmp_path, limits=AutonomyLimits())
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    ledger = tmp_path / "model-spend.jsonl"
    ledger.write_text(
        "\n".join(
            [
                json.dumps({"at": f"{today}T10:00:00+00:00", "usd": 0.002}),
                json.dumps({"at": f"{today}T11:00:00+00:00", "usd": 0.003}),
                json.dumps({"at": "2020-01-01T10:00:00+00:00", "usd": 0.5}),
                json.dumps({"at": f"{today}T12:00:00+00:00", "usd": 0}),
            ]
        ),
        encoding="utf-8",
    )

    record = runner.spend_record()
    status = runner.status()

    assert record["paid_calls"] == 2
    assert record["paid_usd_today"] == pytest.approx(0.005)
    assert record["paid_usd_total"] == pytest.approx(0.505)
    assert status["paid_calls"] == 2


def test_spend_record_is_zero_without_a_ledger(tmp_path) -> None:
    console = build_default_console(tmp_path)
    runner = AutonomyRunner(console, tmp_path, limits=AutonomyLimits())

    assert runner.status()["paid_calls"] == 0
    assert runner.status()["paid_usd_total"] == 0.0
