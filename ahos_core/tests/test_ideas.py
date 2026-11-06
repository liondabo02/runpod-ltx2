"""Idea intake: idea -> department -> tasks -> daemon."""

from __future__ import annotations

from types import SimpleNamespace

from ahos.autonomy import AutonomyLimits, AutonomyRunner
from ahos.ideas import claim_next, complete, pending_tasks, submit
from ahos.owner_console import build_default_console
from ahos.projects import ProjectLink


def test_idea_is_routed_and_split_into_tasks(tmp_path) -> None:
    console = build_default_console(tmp_path)

    idea = submit(console, tmp_path, "çocuklar için yeni bir oyun yapmak istiyorum")

    assert idea.department_id, "fikir bir departmana yönlenmeli"
    assert len(idea.tasks) == 3
    assert all(task["status"] == "pending" for task in idea.tasks)
    assert (tmp_path / "ideas" / f"{idea.idea_id}.json").is_file()


def test_claim_and_complete_cycle(tmp_path) -> None:
    console = build_default_console(tmp_path)
    idea = submit(console, tmp_path, "kafe için sadakat programı tasarla")

    claimed = claim_next(tmp_path)
    assert claimed is not None
    claimed_idea, task = claimed
    assert task["status"] == "running"
    assert claimed_idea.department_id == idea.department_id

    complete(idea.idea_id, task["task_id"], tmp_path, success=True)
    remaining = pending_tasks(tmp_path)
    assert len(remaining) == 2, "bir görev tamamlandı, ikisi bekliyor"


def test_daemon_picks_the_idea_first(tmp_path, monkeypatch) -> None:
    console = build_default_console(tmp_path)
    console.handle("oyun geliştirme departmanı kur")
    project = tmp_path / "proj"
    (project / "www").mkdir(parents=True)
    (project / "www" / "index.html").write_text("<html></html>", encoding="utf-8")
    (project / "tools").mkdir()
    (project / "tools" / "check_offline.py").write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
    console.projects.link(
        ProjectLink(project_id="p", name="P", path=project, department_id="oyun")
    )
    idea = submit(console, tmp_path, "çocuklar için yeni bir oyun yapmak istiyorum")
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
                mission_id="CMD-1",
                steps=[SimpleNamespace(worker_summary="2 dosya değişti; doğrulama geçti")],
            ),
        ),
    )

    runner.run_once()

    assert ran and ran[0] == idea.tasks[0]["title"], "önce fikir görevi çalışmalı"
    remaining = pending_tasks(tmp_path)
    assert len(remaining) == 2, "fikir görevi tamamlandı olarak işaretlenmeli"
