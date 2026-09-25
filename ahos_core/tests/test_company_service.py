from __future__ import annotations

import json
from pathlib import Path

from ahos.autonomous_company import CompanyLoop, PersistentMissionQueue
from ahos.company_service import CompanyService
from ahos.mission_orchestrator import MissionResult, MissionStatus


def _completed(mission):
    return MissionResult(
        mission_id=mission.mission_id,
        objective=mission.objective,
        manager_id="mgr-software-01",
        status=MissionStatus.COMPLETED,
        steps=(),
        reason="done",
    )


def test_service_writes_idle_heartbeat(tmp_path: Path) -> None:
    queue = PersistentMissionQueue(tmp_path / "missions.db")
    service = CompanyService(
        loop=CompanyLoop(queue=queue, executor=_completed),
        heartbeat_path=tmp_path / "heartbeat.json",
        stop_path=tmp_path / "stop",
        poll_seconds=0.01,
    )
    state = service.run_once()
    payload = json.loads((tmp_path / "heartbeat.json").read_text(encoding="utf-8"))
    assert state == "idle"
    assert payload["state"] == "idle"


def test_service_processes_mission(tmp_path: Path) -> None:
    queue = PersistentMissionQueue(tmp_path / "missions.db")
    queue.enqueue(mission_id="m1", objective="local mission", primary_department="software")
    service = CompanyService(
        loop=CompanyLoop(queue=queue, executor=_completed),
        heartbeat_path=tmp_path / "heartbeat.json",
        stop_path=tmp_path / "stop",
        poll_seconds=0.01,
    )
    state = service.run_once()
    payload = json.loads((tmp_path / "heartbeat.json").read_text(encoding="utf-8"))
    assert state == "completed"
    assert payload["state"] == "processed"
    assert payload["mission_id"] == "m1"


def test_stop_file_is_honored(tmp_path: Path) -> None:
    queue = PersistentMissionQueue(tmp_path / "missions.db")
    stop = tmp_path / "stop"
    stop.write_text("stop", encoding="utf-8")
    service = CompanyService(
        loop=CompanyLoop(queue=queue, executor=_completed),
        heartbeat_path=tmp_path / "heartbeat.json",
        stop_path=stop,
        poll_seconds=0.01,
    )
    assert service.should_stop() is True


def test_service_runs_automation_steps_while_mission_queue_is_idle(tmp_path: Path) -> None:
    queue = PersistentMissionQueue(tmp_path / "missions.db")
    calls = []
    service = CompanyService(
        loop=CompanyLoop(queue=queue, executor=_completed),
        heartbeat_path=tmp_path / "heartbeat.json",
        stop_path=tmp_path / "stop",
        automation_steps=(lambda: calls.append("coding-dispatch") or "coding:1",),
    )
    assert service.run_once() == "idle"
    payload = json.loads((tmp_path / "heartbeat.json").read_text(encoding="utf-8"))
    assert calls == ["coding-dispatch"]
    assert payload["automation_results"] == ["coding:1"]
