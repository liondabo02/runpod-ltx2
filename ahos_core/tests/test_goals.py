"""Goal continuation: a broad objective runs to the end, step by step."""

from __future__ import annotations

from types import SimpleNamespace

from ahos import goals
from ahos.autonomy import AutonomyLimits, AutonomyRunner
from ahos.owner_console import build_default_console
from ahos.projects import ProjectLink


def test_goal_is_created_with_ordered_steps(tmp_path) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()

    goal = goals.create(runtime, "Stüdyoyu geliştir", "oyun")

    assert goal.steps and all(step.status == "pending" for step in goal.steps)
    assert goal.progress == 0.0
    assert (runtime / "goals" / f"{goal.goal_id}.json").is_file()


def test_creation_is_idempotent(tmp_path) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()

    first = goals.create(runtime, "Stüdyoyu geliştir", "oyun")
    second = goals.create(runtime, "Stüdyoyu geliştir", "oyun")

    assert first.goal_id == second.goal_id
    assert len(goals.all_goals(runtime)) == 1


def test_steps_advance_and_complete(tmp_path) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    goal = goals.create(runtime, "Stüdyoyu geliştir", "oyun", steps=["bir", "iki"])

    for step in goal.steps:
        goals.advance(runtime, goal.goal_id, step.step_id, success=True, note="tamam")

    final = goals.load(runtime, goal.goal_id)
    assert final is not None and final.status == "done"
    assert final.progress == 1.0


def test_failing_step_is_blocked_after_two_tries(tmp_path) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    goal = goals.create(runtime, "Stüdyoyu geliştir", "oyun", steps=["zor adım"])

    goals.advance(runtime, goal.goal_id, goal.steps[0].step_id, success=False, note="olmadı")
    goals.advance(runtime, goal.goal_id, goal.steps[0].step_id, success=False, note="yine olmadı")

    final = goals.load(runtime, goal.goal_id)
    assert final is not None
    assert final.steps[0].status == "blocked"
    assert final.steps[0].attempts == 2


def test_next_step_skips_blocked_ones(tmp_path) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    goal = goals.create(runtime, "Stüdyoyu geliştir", "oyun", steps=["a", "b"])
    goals.advance(runtime, goal.goal_id, "s1", success=False, note="x")
    goals.advance(runtime, goal.goal_id, "s1", success=False, note="x")

    found = goals.next_step(runtime)

    assert found is not None
    _goal, step = found
    assert step.step_id == "s2"


def test_daemon_runs_a_goal_step_first(tmp_path, monkeypatch) -> None:
    console = build_default_console(tmp_path)
    console.handle("çizgi film departmanı kur")
    project = tmp_path / "proj"
    (project / "www").mkdir(parents=True)
    (project / "www" / "index.html").write_text("<html></html>", encoding="utf-8")
    (project / "tools").mkdir()
    (project / "tools" / "check_offline.py").write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
    console.projects.link(
        ProjectLink(project_id="p", name="P", path=project, department_id="creative")
    )
    goal = goals.create(tmp_path, "Stüdyoyu geliştir", "creative")
    runner = AutonomyRunner(console, tmp_path, limits=AutonomyLimits(max_missions=1))
    ran: list[str] = []
    monkeypatch.setattr(
        runner.console,
        "run_department_mission",
        lambda spec, objective, **k: ran.append(objective)
        or SimpleNamespace(
            status="routed",
            message="tamam",
            mission=SimpleNamespace(
                mission_id="CMD-G1",
                steps=[SimpleNamespace(worker_summary="1 dosya değişti; doğrulama geçti")],
            ),
        ),
    )

    runner.run_once()

    assert ran and ran[0] == goal.steps[0].title
    updated = goals.load(tmp_path, goal.goal_id)
    assert updated is not None and updated.steps[0].status == "done"
