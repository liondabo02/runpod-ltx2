"""Self-improvement queue: the worker picks up its own weakest link."""

from __future__ import annotations

import json
from types import SimpleNamespace

from ahos.autonomy import AutonomyLimits, AutonomyRunner
from ahos.owner_console import build_default_console
from ahos.projects import ProjectLink


def _runner(tmp_path) -> AutonomyRunner:
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
    return AutonomyRunner(console, tmp_path, limits=AutonomyLimits(max_missions=2))


def _backlog(tmp_path, title: str) -> None:
    (tmp_path / "self-improvement.jsonl").write_text(
        json.dumps({"department": "oyun", "title": title, "why": "kalite"}) + "\n",
        encoding="utf-8",
    )


def test_self_improvement_task_is_picked_before_the_cycle(tmp_path, monkeypatch) -> None:
    runner = _runner(tmp_path)
    title = "Sistem kalitesi: teslimat yok nedenini azalt"
    _backlog(tmp_path, title)
    ran: list[str] = []
    monkeypatch.setattr(
        runner.console,
        "run_department_mission",
        lambda spec, objective, **k: ran.append(objective)
        or SimpleNamespace(
            status="routed",
            message="tamam",
            mission=SimpleNamespace(
                mission_id="CMD-9",
                steps=[SimpleNamespace(worker_summary="3 dosya değişti; doğrulama geçti")],
            ),
        ),
    )

    runner.run_once()

    assert ran == [title], "önce kalite görevi çalışmalı"
    done = (tmp_path / "self-improvement-done.jsonl").read_text(encoding="utf-8")
    assert title in done, "başarılı iş tamamlandı olarak işaretlenmeli"


def test_completed_improvement_is_not_repeated(tmp_path, monkeypatch) -> None:
    runner = _runner(tmp_path)
    title = "Sistem kalitesi: kabul düşüşünü azalt"
    _backlog(tmp_path, title)
    (tmp_path / "self-improvement-done.jsonl").write_text(
        json.dumps({"title": title}) + "\n", encoding="utf-8"
    )
    ran: list[str] = []
    monkeypatch.setattr(
        runner.console,
        "run_department_mission",
        lambda spec, objective, **k: ran.append(objective)
        or SimpleNamespace(
            status="routed",
            message="tamam",
            mission=SimpleNamespace(
                mission_id="CMD-10",
                steps=[SimpleNamespace(worker_summary="1 dosya değişti; doğrulama geçti")],
            ),
        ),
    )

    runner.run_once()

    assert title not in ran, "tamamlanmış kalite görevi tekrar çalışmamalı"
