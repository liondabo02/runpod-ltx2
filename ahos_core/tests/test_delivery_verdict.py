"""Positive and negative checks for the delivery verdict.

A routed mission is not a delivery. It must have changed real files and the
project's own acceptance gate must pass; a browser load alone proves nothing.
These tests run in an isolated temporary project, never the live one.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from ahos.autonomy import AutonomyLimits, AutonomyRunner
from ahos.owner_console import build_default_console
from ahos.projects import ProjectLink


def _project(tmp_path: Path, gate_exit: int | None) -> Path:
    root = tmp_path / "proj"
    (root / "www").mkdir(parents=True)
    (root / "www" / "index.html").write_text("<html><body>oyun</body></html>", encoding="utf-8")
    if gate_exit is not None:
        (root / "tools").mkdir()
        (root / "tools" / "check_offline.py").write_text(
            f"import sys\nsys.exit({gate_exit})\n", encoding="utf-8"
        )
    return root


def _runner(tmp_path: Path, project: Path) -> AutonomyRunner:
    console = build_default_console(tmp_path)
    console.handle("oyun geliştirme departmanı kur")
    console.projects.link(
        ProjectLink(project_id="p", name="P", path=project, department_id="oyun")
    )
    return AutonomyRunner(console, tmp_path, limits=AutonomyLimits(max_missions=3))


def _result(summary: str, mission_id: str = "CMD-1"):
    return SimpleNamespace(
        status="routed",
        message="görev tamamlandı",
        mission=SimpleNamespace(
            mission_id=mission_id,
            steps=[SimpleNamespace(worker_summary=summary)],
        ),
    )


def test_positive_real_change_with_passing_gate_is_a_delivery(tmp_path) -> None:
    runner = _runner(tmp_path, _project(tmp_path, gate_exit=0))

    delivered, verdict = runner.delivery_verdict(_result("2 dosya değişti; doğrulama geçti"), "oyun")

    assert delivered is True
    assert "kabul kapısı geçti" in verdict


def test_negative_zero_changes_is_never_a_delivery(tmp_path) -> None:
    runner = _runner(tmp_path, _project(tmp_path, gate_exit=0))

    delivered, verdict = runner.delivery_verdict(_result("0 dosya değişti; doğrulama geçti"), "oyun")

    assert delivered is False
    assert "0 dosya" in verdict


def test_negative_failing_gate_blocks_the_delivery(tmp_path) -> None:
    runner = _runner(tmp_path, _project(tmp_path, gate_exit=1))

    delivered, verdict = runner.delivery_verdict(_result("3 dosya değişti; doğrulama geçti"), "oyun")

    assert delivered is False
    assert "kabul kapısı düştü" in verdict


def test_negative_browser_only_project_is_not_accepted(tmp_path) -> None:
    # Kapı yok: sayfa açılsa bile kabul testi sayılmaz.
    runner = _runner(tmp_path, _project(tmp_path, gate_exit=None))

    delivered, verdict = runner.delivery_verdict(_result("1 dosya değişti; tarayıcı geçti"), "oyun")

    assert delivered is False
    assert "kabul kapısı yok" in verdict


def test_negative_worker_reporting_no_change_count_is_not_accepted(tmp_path) -> None:
    runner = _runner(tmp_path, _project(tmp_path, gate_exit=0))

    delivered, verdict = runner.delivery_verdict(_result("rapor üretildi"), "oyun")

    assert delivered is False
    assert "bildirmedi" in verdict


def test_acceptance_requirement_can_be_disabled_explicitly(tmp_path, monkeypatch) -> None:
    runner = _runner(tmp_path, _project(tmp_path, gate_exit=1))
    monkeypatch.setenv("AHOS_REQUIRE_ACCEPTANCE", "0")

    delivered, verdict = runner.delivery_verdict(_result("2 dosya değişti"), "oyun")

    assert delivered is True
    assert "devre dışı" in verdict


def test_run_once_counts_a_zero_change_mission_as_failure(tmp_path, monkeypatch) -> None:
    runner = _runner(tmp_path, _project(tmp_path, gate_exit=0))
    monkeypatch.setattr(
        runner.console,
        "run_department_mission",
        lambda *a, **k: _result("0 dosya değişti; doğrulama geçti"),
    )

    result = runner.run_once()

    assert result is not None
    assert runner.state.failed == 1
    assert runner.state.executed == 0
    assert "0 dosya" in runner.state.last_reason
