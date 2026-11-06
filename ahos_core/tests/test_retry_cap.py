from __future__ import annotations

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


def test_blocked_mission_retries_are_bounded(tmp_path) -> None:
    """Aynı engelli görev sonsuz kez yeniden denenmemeli.

    Proje bağlı olmadığı için her deneme `blocked-unverified` ile kapanır;
    tekrar gönderim en fazla `max_attempts` (2) kez yürütücü çağırmalı.
    """

    console = build_default_console(tmp_path)
    console.handle("çizgi film departmanı kur")
    spec = console.book.require("creative")
    calls: list[str] = []

    def counting(item: WorkItem, worker_id: str) -> WorkerExecutionResult:
        calls.append(item.task_id)
        return _result(item, worker_id)

    missions: list[str] = []
    for _ in range(4):
        outcome = console.run_department_mission(spec, "sınırlı tekrar", executor=counting)
        missions.append(outcome.mission.mission_id if outcome.mission else "")

    distinct_runs = {task.split(":")[0] for task in calls}
    assert len(distinct_runs) <= 2, f"engelli görev {len(distinct_runs)} kez çalıştı: {sorted(distinct_runs)}"
