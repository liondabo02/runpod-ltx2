from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ahos.departments import DepartmentBook
from ahos.holding_office import (
    HOLDING_DEPARTMENT_ID,
    SECURITY_DEPARTMENT_ID,
    HoldingOffice,
    ensure_builtin_departments,
    holding_department_spec,
    security_department_spec,
)
from ahos.owner_console import build_default_console


def test_holding_and_security_departments_are_seeded(tmp_path) -> None:
    console = build_default_console(tmp_path)

    holding = console.book.require(HOLDING_DEPARTMENT_ID)
    security = console.book.require(SECURITY_DEPARTMENT_ID)

    assert holding.name.startswith("Holding")
    assert holding.manager.worker_id == "ceo-01"
    assert holding.manager.reports_to is None
    assert holding.source == "holding"

    assert security.source == "holding"
    assert len(security.workers) == 5
    assert security.manager.worker_id == "guvenlik-manager"
    assert {worker.team_id for worker in security.workers} == {
        "guvenlik-leadership",
        "guvenlik-audit",
        "guvenlik-release",
    }


def test_ensure_builtin_departments_is_idempotent() -> None:
    book = DepartmentBook(seed=True)
    first = ensure_builtin_departments(book)
    second = ensure_builtin_departments(book)

    assert {spec.department_id for spec in first} == {
        HOLDING_DEPARTMENT_ID,
        SECURITY_DEPARTMENT_ID,
        "ai-platform",
    }
    assert len(book.all()) == 14
    assert {spec.department_id for spec in second} == {
        HOLDING_DEPARTMENT_ID,
        SECURITY_DEPARTMENT_ID,
        "ai-platform",
    }


def test_specs_validate_and_have_manager() -> None:
    for spec in (holding_department_spec(), security_department_spec()):
        assert spec.validate() is spec
        assert spec.manager.reports_to is None
        assert spec.workers[0].worker_id.endswith(("01", "manager"))


def test_assessment_counts_missions_and_projects(tmp_path) -> None:
    console = build_default_console(tmp_path)
    spec = console.book.require("quality")
    console.run_department_mission(spec, "küçük görev")

    statuses = HoldingOffice(console).assessment()
    quality = next(status for status in statuses if status.department_id == "quality")

    assert quality.missions >= 1
    assert quality.workers == 2
    assert quality.blocked == 1


def test_ceo_prefers_unblocking_blocked_departments(tmp_path) -> None:
    console = build_default_console(tmp_path)
    office = HoldingOffice(console)

    directive = office.next_directive()

    assert directive is not None
    assert directive.department_id != HOLDING_DEPARTMENT_ID
    assert directive.priority >= 1


def test_ceo_directive_targets_stale_bound_project(tmp_path) -> None:
    console = build_default_console(tmp_path)
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    (project_dir / "index.html").write_text("<html></html>", encoding="utf-8")

    from ahos.projects import ProjectLink

    console.projects.link(
        ProjectLink(
            project_id="demo",
            name="Demo",
            path=project_dir,
            department_id="software",
            kind="html5-app",
        )
    )

    office = HoldingOffice(console)
    later = datetime.now(timezone.utc) + timedelta(days=2)
    directive = office.next_directive(now=later)

    assert directive is not None
    assert directive.kind == "project_advance"
    assert directive.department_id == "software"


def test_brief_contains_decision(tmp_path) -> None:
    console = build_default_console(tmp_path)

    brief = HoldingOffice(console).brief()

    assert "CEO" in brief
    assert "Holding durumu" in brief
    assert "Karar:" in brief


def test_ceo_runs_a_directive_through_the_console(tmp_path) -> None:
    console = build_default_console(tmp_path)
    office = HoldingOffice(console)

    result = office.run_once()

    assert result is not None
    assert result.status in {"routed", "blocked"}
    assert result.mission is not None


def test_managers_are_listed_with_reporting_lines(tmp_path) -> None:
    console = build_default_console(tmp_path)
    office = HoldingOffice(console)

    managers = {department_id: manager for department_id, _, manager in office.managers()}

    assert managers["quality"] == "mgr-quality-01"
    assert managers[HOLDING_DEPARTMENT_ID] == "ceo-01"
