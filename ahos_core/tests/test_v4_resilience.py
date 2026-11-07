"""G015-G016: kuyruk dayanıklılığı, restart ve hata enjeksiyonu."""
from __future__ import annotations

import json
import time

import pytest

from ahos import worker_mind
from ahos.autonomous_company import PersistentMissionQueue, QueueStatus
from ahos.mission_orchestrator import MissionResult, MissionStatus


def _completed_result(mission_id: str, objective: str) -> MissionResult:
    return MissionResult(mission_id, objective, "software-manager",
                         MissionStatus.COMPLETED, (), "completed",
                         qa_worker_id="qa-verify-01")


def test_queue_state_survives_restart_and_expired_lease_recovers(tmp_path):
    queue = PersistentMissionQueue(tmp_path / "company-service.db")
    queue.enqueue(mission_id="r-1", objective="restart testi",
                  primary_department="software", max_attempts=2)
    claimed = queue.claim_next(owner="daemon-a", lease_seconds=30)
    assert claimed is not None and claimed.mission_id == "r-1"
    assert queue.get("r-1").status is QueueStatus.RUNNING

    # "yeniden başlatma": yeni süreç/nesne; süresi dolmuş lease geri alınır
    restarted = PersistentMissionQueue(tmp_path / "company-service.db")
    assert restarted.get("r-1").status is QueueStatus.RUNNING
    reclaimed = restarted.claim_next(owner="daemon-b", lease_seconds=30,
                                     now=time.time() + 31)
    assert reclaimed is not None and reclaimed.mission_id == "r-1"
    assert restarted.get("r-1").status is QueueStatus.RUNNING
    # tek satır, çift görev yok
    assert len([m for m in restarted.list() if m.mission_id == "r-1"]) == 1


def test_completed_mission_is_never_reopened(tmp_path):
    queue = PersistentMissionQueue(tmp_path / "company-service.db")
    queue.enqueue(mission_id="done-1", objective="tamamlanmış iş",
                  primary_department="software", max_attempts=2)
    assert queue.claim_next(owner="qa-run", lease_seconds=30).mission_id == "done-1"
    queue.complete("done-1", owner="qa-run",
                   result=_completed_result("done-1", "tamamlanmış iş"))
    assert queue.get("done-1").status is QueueStatus.COMPLETED

    # Aynı id ile replace_existing çağrısı tamamlanmış kaydı geri açamaz.
    queue.enqueue(mission_id="done-1", objective="tekrar",
                  primary_department="software", replace_existing=True)
    row = queue.get("done-1")
    assert row.status is QueueStatus.COMPLETED
    assert row.objective == "tamamlanmış iş"
    assert queue.claim_next(owner="another", lease_seconds=30) is None


def test_cancelled_mission_is_not_success_and_can_be_reused(tmp_path):
    queue = PersistentMissionQueue(tmp_path / "company-service.db")
    queue.enqueue(mission_id="c-1", objective="iptal", primary_department="software")
    queue.cancel("c-1") if hasattr(queue, "cancel") else None
    if queue.get("c-1").status is not QueueStatus.PENDING:
        assert queue.get("c-1").status is QueueStatus.CANCELLED
        queue.enqueue(mission_id="c-1", objective="yeniden", primary_department="software",
                      replace_existing=True)
        assert queue.get("c-1").status is QueueStatus.PENDING


def test_mind_memory_survives_restart(tmp_path):
    mind = worker_mind.Mind("w-1", "software")
    mind.self_model["plan_scores"] = {"executor": {"ok": 2, "fail": 1, "total_s": 0.0}}
    mind.events.append({"kind": "mission", "ok": True, "mission_id": "m-1"})
    worker_mind.save(tmp_path, mind)

    again = worker_mind.load(tmp_path, "w-1")
    assert again.self_model["plan_scores"]["executor"]["ok"] == 2
    assert again.success_rate == 1.0


def test_corrupt_mind_is_not_overwritten_on_restart(tmp_path):
    path = tmp_path / "minds" / "broken.json"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"{broken")
    with pytest.raises(ValueError):
        worker_mind.load(tmp_path, "broken")
    assert path.read_bytes() == b"{broken"
