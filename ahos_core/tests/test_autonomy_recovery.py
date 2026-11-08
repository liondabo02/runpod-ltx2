"""Cancellation and crash-recovery wiring at the autonomy level."""

from __future__ import annotations

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
    (project / "tools" / "check_offline.py").write_text(
        "import sys\nsys.exit(0)\n", encoding="utf-8"
    )
    console.projects.link(
        ProjectLink(project_id="p", name="P", path=project, department_id="oyun")
    )
    return AutonomyRunner(console, tmp_path, limits=AutonomyLimits(max_missions=3))


def _result(status: str, message: str, summary: str = ""):
    return SimpleNamespace(
        status=status,
        message=message,
        mission=SimpleNamespace(
            mission_id="CMD-1",
            steps=[SimpleNamespace(worker_summary=summary)] if summary else [],
        ),
    )


def test_stop_file_cancels_before_the_next_attempt(tmp_path, monkeypatch) -> None:
    runner = _runner(tmp_path)
    calls: list[str] = []

    def fake_blocked_reason():
        calls.append("check")
        # İlk çağrı (görev seçimi öncesi) serbest, ikincisi iptal sinyali.
        return "" if len(calls) == 1 else "acil durdurma"

    monkeypatch.setattr(runner, "_blocked_reason", fake_blocked_reason)
    ran: list[str] = []
    monkeypatch.setattr(
        runner.console,
        "run_department_mission",
        lambda *a, **k: ran.append("ran") or _result("blocked", "olmadı"),
    )

    result = runner.run_once()

    assert result is None
    assert ran == [], "iptal sonrası yeni deneme başlamamalı"
    assert runner.state.status == "stopped"
    assert "iptal" in runner.state.last_reason


def test_claim_failure_triggers_one_recovery(tmp_path, monkeypatch) -> None:
    runner = _runner(tmp_path)
    recovered: list[int] = []
    monkeypatch.setattr(runner, "_recover_queue", lambda: recovered.append(1) or {"reopened_stuck": 2})
    monkeypatch.setattr(
        runner.console,
        "run_department_mission",
        lambda *a, **k: _result("blocked", "görev sahiplenilemedi (durum=blocked, lease=-)"),
    )

    runner.run_once()

    assert recovered == [1]
    assert "kurtarma" in runner.state.last_reason


def test_recovery_is_not_triggered_for_unrelated_failures(tmp_path, monkeypatch) -> None:
    runner = _runner(tmp_path)
    recovered: list[int] = []
    monkeypatch.setattr(runner, "_recover_queue", lambda: recovered.append(1) or {})
    monkeypatch.setattr(
        runner.console,
        "run_department_mission",
        lambda *a, **k: _result("blocked", "üretim yürütücüsü bağlı değil"),
    )

    runner.run_once()

    assert recovered == []
