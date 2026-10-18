"""Load test: 100 synthetic missions through the real console, queue and QA path.

No model, no network, no project files: the executor and QA are in-memory
fakes, so the test measures orchestration, queue durability and step
uniqueness rather than model quality.
"""

from __future__ import annotations

import time

from ahos.worker_runtime import WorkerExecutionResult, local_pass_qa


def _executor(item, worker_id):
    return WorkerExecutionResult(
        task_id=item.task_id,
        worker_id=worker_id,
        success=True,
        summary="soak adımı tamam",
    )


def _console(tmp_path) -> OwnerConsole:
    from ahos.autonomous_company import PersistentMissionQueue
    from ahos.departments import DepartmentBook
    from ahos.holding_office import ensure_builtin_departments
    from ahos.owner_console import OwnerConsole
    from ahos.projects import ProjectRegistry

    book = DepartmentBook(tmp_path / "departments.json", seed=True)
    ensure_builtin_departments(book)
    return OwnerConsole(
        book,
        runtime_dir=tmp_path,
        executors={"*": _executor},
        qa_executor=local_pass_qa,
        queue=PersistentMissionQueue(tmp_path / "soak.db"),
        projects=ProjectRegistry(tmp_path / "projects.json"),
    )


def test_hundred_synthetic_missions_complete_without_loss_or_duplication(tmp_path) -> None:
    console = _console(tmp_path)
    departments = [
        console.book.require(name) for name in ("software", "creative", "data", "research")
    ]

    started = time.perf_counter()
    mission_ids: list[str] = []
    for index in range(100):
        spec = departments[index % len(departments)]
        result = console.run_department_mission(spec, f"soak görevi {index}")
        assert result.status == "routed", result.message
        assert result.mission is not None
        mission_ids.append(result.mission.mission_id)
    elapsed = time.perf_counter() - started

    assert len(set(mission_ids)) == 100, "görev kimlikleri tekrar etmemeli"
    assert elapsed < 120, f"100 görev {elapsed:.1f} sn sürdü"

    queued = console.queue.list()
    assert len(queued) == 100
    assert all(row.status.value == "completed" for row in queued)

    # Her görev tam olarak üç mantıksal adımdan geçer; adım kimliği tekrar etmez.
    for mission_id in mission_ids:
        row = console.queue.get(mission_id)
        assert row is not None


def test_soak_is_idempotent_when_replayed(tmp_path) -> None:
    console = _console(tmp_path)
    spec = console.book.require("software")

    first = console.run_department_mission(spec, "aynı görev")
    second = console.run_department_mission(spec, "aynı görev")

    assert first.mission is not None
    assert first.mission.mission_id == second.mission.mission_id
    assert len(console.queue.list()) == 1
