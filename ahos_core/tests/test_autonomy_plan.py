from __future__ import annotations

import json

import pytest

from ahos.autonomy import AutonomyLimits, AutonomyRunner
from ahos.owner_console import build_default_console
from ahos.projects import ProjectLink


def _runner(tmp_path) -> AutonomyRunner:
    console = build_default_console(tmp_path)
    console.handle("oyun geliştirme departmanı kur")
    project = tmp_path / "proj"
    (project / "www").mkdir(parents=True)
    (project / "www" / "index.html").write_text("<html></html>", encoding="utf-8")
    console.projects.link(
        ProjectLink(project_id="p", name="Mipiluna", path=project, department_id="oyun")
    )
    return AutonomyRunner(console, tmp_path, limits=AutonomyLimits(max_missions=3))


def _fake_plan(monkeypatch, items):
    from ahos import model_planner

    monkeypatch.setattr(model_planner, "propose_objectives", lambda *a, **k: list(items))


def test_plan_directive_uses_the_model_and_consumes_items(tmp_path, monkeypatch) -> None:
    runner = _runner(tmp_path)
    _fake_plan(
        monkeypatch,
        [
            {"department": "oyun", "title": "Kartlara sesli geri bildirim ekle", "why": "erişim"},
            {"department": "oyun", "title": "Ana sayfaya günün oyunu şeridi ekle", "why": "tutundurma"},
        ],
    )

    first = runner.plan_directive()

    assert first is not None
    assert first.kind == "model_plan"
    assert first.department_id == "oyun"
    assert first.objective == "Kartlara sesli geri bildirim ekle"

    second = runner.plan_directive()

    assert second is not None
    assert second.objective == "Ana sayfaya günün oyunu şeridi ekle"

    assert runner.plan_directive() is None, "plan tükendiğinde yeni istek yapılmamalı"


def test_plan_directive_skips_excluded_departments(tmp_path, monkeypatch) -> None:
    runner = _runner(tmp_path)
    _fake_plan(
        monkeypatch,
        [{"department": "oyun", "title": "Yeni bir renk paleti seçeneği ekle", "why": ""}],
    )

    assert runner.plan_directive({"oyun"}) is None


def test_plan_directive_skips_objectives_already_executed(tmp_path, monkeypatch) -> None:
    runner = _runner(tmp_path)
    title = "Yeni bir renk paleti seçeneği ekle"
    runner._record(runner._key("oyun", title), "CMD-1", "oyun", "completed")
    _fake_plan(monkeypatch, [{"department": "oyun", "title": title, "why": ""}])

    assert runner.plan_directive() is None


def test_planner_only_sees_departments_with_projects(tmp_path, monkeypatch) -> None:
    from ahos import model_planner

    runner = _runner(tmp_path)
    captured: dict = {}

    def fake_propose(departments, projects, recent, limit=3, **kwargs):
        captured["departments"] = dict(departments)
        return [{"department": "oyun", "title": "Ana sayfaya günün oyunu şeridi ekle", "why": ""}]

    monkeypatch.setattr(model_planner, "propose_objectives", fake_propose)

    runner.plan_directive()

    assert set(captured["departments"]) == {"oyun"}, "projesiz departman plana girmemeli"


def test_plan_directive_skips_departments_without_projects(tmp_path, monkeypatch) -> None:
    runner = _runner(tmp_path)
    _fake_plan(
        monkeypatch,
        [
            {"department": "destek", "title": "Destek için olay müdahale listesi oluştur", "why": ""},
            {"department": "oyun", "title": "Ana sayfaya günün oyunu şeridi ekle", "why": ""},
        ],
    )

    directive = runner.plan_directive()

    assert directive is not None
    assert directive.department_id == "oyun", "projesi olmayan departman seçilmemeli"


def test_plan_directive_is_idle_without_a_model(tmp_path, monkeypatch) -> None:
    runner = _runner(tmp_path)
    _fake_plan(monkeypatch, [])

    assert runner.plan_directive() is None


def test_plan_file_is_day_scoped(tmp_path, monkeypatch) -> None:
    runner = _runner(tmp_path)
    _fake_plan(
        monkeypatch,
        [{"department": "oyun", "title": "Ana sayfaya günün oyunu şeridi ekle", "why": ""}],
    )
    runner.plan_directive()

    payload = json.loads(runner.plan_path.read_text(encoding="utf-8"))
    payload["day"] = "2000-01-01"
    runner.plan_path.write_text(json.dumps(payload), encoding="utf-8")

    _fake_plan(
        monkeypatch,
        [{"department": "oyun", "title": "Yeni bir renk paleti seçeneği ekle", "why": ""}],
    )
    directive = runner.plan_directive()

    assert directive is not None
    assert directive.objective == "Yeni bir renk paleti seçeneği ekle"
