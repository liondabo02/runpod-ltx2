from __future__ import annotations

from types import SimpleNamespace

from ahos.autonomous_company import PersistentMissionQueue, QueueStatus
from ahos.mission_orchestrator import MissionResult, MissionStatus
from ahos.queue_drain import drain


class FakeBook:
    def __init__(self, departments: set[str]) -> None:
        self.departments = departments

    def get(self, department_id: str):
        return SimpleNamespace(department_id=department_id) if department_id in self.departments else None


class FakeConsole:
    def __init__(self, tmp_path, departments: set[str]) -> None:
        self.runtime_dir = tmp_path
        self.queue = PersistentMissionQueue(tmp_path / "company-service.db")
        self.book = FakeBook(departments)
        self.executed: list[str] = []

    def _execute(self, spec, objective, mission_id, executor=None):
        self.executed.append(mission_id)
        return MissionResult(
            mission_id=mission_id,
            objective=objective,
            manager_id=None,
            status=MissionStatus.COMPLETED,
            steps=(),
            reason="tamam",
        )

    def _record(self, mission_id, owner, result) -> None:
        self.queue.complete(mission_id, owner=owner, result=result)


def test_pending_mission_is_executed_and_completed(tmp_path) -> None:
    console = FakeConsole(tmp_path, {"oyun"})
    console.queue.enqueue(
        mission_id="m-1", objective="iş", primary_department="oyun"
    )

    report = drain(console, limit=5)

    assert report["executed"] == ["m-1"]
    assert console.executed == ["m-1"]
    assert console.queue.get("m-1").status is QueueStatus.COMPLETED


def test_missing_department_blocks_instead_of_dropping(tmp_path) -> None:
    console = FakeConsole(tmp_path, set())
    console.queue.enqueue(
        mission_id="m-2", objective="iş", primary_department="kayip"
    )

    report = drain(console, limit=5)

    assert report["blocked"] == ["m-2"]
    mission = console.queue.get("m-2")
    assert mission.status is QueueStatus.BLOCKED
    assert "departman artık yok" in (mission.last_error or "")


def test_dry_run_does_not_execute(tmp_path) -> None:
    console = FakeConsole(tmp_path, {"oyun"})
    console.queue.enqueue(
        mission_id="m-3", objective="iş", primary_department="oyun"
    )

    report = drain(console, limit=5, dry_run=True)

    assert report["would_run"] == ["m-3"]
    assert console.executed == []
    assert console.queue.get("m-3").status is QueueStatus.PENDING
