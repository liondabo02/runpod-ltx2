from __future__ import annotations

import threading
import time

import pytest

from ahos.owner_console import build_default_console
from ahos.worker_runtime import WorkItem, WorkerExecutionResult


def _result(item: WorkItem, worker_id: str) -> WorkerExecutionResult:
    return WorkerExecutionResult(
        task_id=item.task_id,
        worker_id=worker_id,
        success=True,
        summary="ok",
        artifacts=(),
    )


def test_custom_executor_cannot_bypass_unverified_qa(tmp_path) -> None:
    """Explicit executor, proje yok → bağımsız kabul yok → kapalı QA reddi."""

    console = build_default_console(tmp_path)
    console.handle("çizgi film departmanı kur")
    spec = console.book.require("creative")

    def executor(item: WorkItem, worker_id: str) -> WorkerExecutionResult:
        return _result(item, worker_id)

    result = console.run_department_mission(spec, "custom executor görevi", executor=executor)

    assert result.status == "blocked"
    assert "blocked-unverified" in result.message or "fail-closed" in result.message


def test_timeout_marks_executor_as_not_cancel_safe(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AHOS_MISSION_TIMEOUT_SECONDS", "0.2")
    monkeypatch.setenv("AHOS_CANCEL_WAIT_SECONDS", "0.2")
    console = build_default_console(tmp_path)
    console.handle("çizgi film departmanı kur")
    spec = console.book.require("creative")
    stop = threading.Event()

    def slow(item: WorkItem, worker_id: str) -> WorkerExecutionResult:
        stop.wait(2.0)
        return _result(item, worker_id)

    result = console.run_department_mission(spec, "kesilemez yürütücü", executor=slow)
    stop.set()

    assert result.status in {"blocked", "error"}
    assert "kesilebilir değil" in result.message


def test_step_identities_are_unique_per_mission(tmp_path) -> None:
    """brief/produce/review ayrı adımlardır; aynı kimlik tekrarlanmaz."""

    from ahos.projects import ProjectLink

    console = build_default_console(tmp_path)
    console.handle("çizgi film departmanı kur")
    spec = console.book.require("creative")
    project = tmp_path / "proj"
    (project / "www").mkdir(parents=True)
    (project / "www" / "index.html").write_text(
        '<html><body><script src="app.js"></script></body></html>', encoding="utf-8"
    )
    (project / "www" / "app.js").write_text("// app\n", encoding="utf-8")
    console.projects.link(
        ProjectLink(
            project_id="p",
            name="P",
            path=project,
            department_id="creative",
        )
    )

    created: list[str] = []

    def executor(item: WorkItem, worker_id: str) -> WorkerExecutionResult:
        created.append(item.task_id)
        artifact = console.artifacts_root / f"{item.task_id.replace(':', '_')}.md"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text("kanıt", encoding="utf-8")
        return WorkerExecutionResult(
            task_id=item.task_id,
            worker_id=worker_id,
            success=True,
            summary="ok",
            artifacts=(str(artifact),),
        )

    result = console.run_department_mission(spec, "adım kimliği testi", executor=executor)
    steps = list(result.mission.steps) if result.mission else []
    ids = [step.step.step_id for step in steps]

    assert ids, "görev hiç adım üretmedi"
    assert len(ids) == len(set(ids)), f"tekrarlanan adım kimliği: {ids}"
    assert {"brief", "produce"}.issubset(set(ids))
