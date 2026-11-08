"""G007: 20 başarısızlık senaryosunda hata → düzeltme → test → doğrulama zinciri.

Her senaryo gerçek kuyruk/drain/QA yolunu kullanır (tmp_path):
1. Bilinçli hata ile görev çalışır → blocked + neden sınıfı.
2. İşçi profiline kanıtlı olay + yansıma yazılır (ders nedeni içerir).
3. Görev yeniden kuyruğa alınır, düzeltilmiş yürütücü ile çalışır → completed.
4. Başarı yansıması "doğrulandı" der; prosedürel hafızada fail ve ok birlikte kalır.

Ayrıca başarısız yeni yöntemin eski tercih edilen yöntemi ezmediği doğrulanır.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from ahos import cognitive_memory as cm
from ahos.autonomous_company import PersistentMissionQueue, QueueStatus
from ahos.consensus import score_plan
from ahos.mission_orchestrator import MissionResult, MissionStatus
from ahos.queue_drain import drain
from ahos.worker_mind import load as load_mind

CASES = [
    ("işlem zaman aşımı", "timeout"),
    ("timeout 240s", "timeout"),
    ("model yanıt vermedi", "model_unavailable"),
    ("model unavailable", "model_unavailable"),
    ("kabul testi başarısız", "acceptance_failed"),
    ("acceptance failed: check_offline", "acceptance_failed"),
    ("dosya değişmedi", "no_delivery"),
    ("no delivery: changed_files 0", "no_delivery"),
    ("kilit sahipli", "lock"),
    ("lock: stale lease", "lock"),
    ("yetki reddedildi", "permission"),
    ("permission denied", "permission"),
    ("şema geçersiz", "schema"),
    ("schema mismatch", "schema"),
    ("bilinmeyen hata", "other"),
    ("other failure", "other"),
    ("işlem zaman aşımı 2", "timeout"),
    ("model boş yanıt", "model_unavailable"),
    ("kabul kapısı reddetti", "acceptance_failed"),
    ("değişiklik yok", "no_delivery"),
]


class Console:
    def __init__(self, runtime, queue, reason, success=False):
        self.runtime_dir = runtime
        self.book = SimpleNamespace(get=lambda dep: SimpleNamespace(department_id=dep))
        self.queue = queue
        self.reason = reason
        self.success = success

    def _project_for_department(self, dep):
        return None

    def _execute(self, spec, objective, mission_id, executor=None):
        if self.success:
            return MissionResult(mission_id, objective, "software-manager",
                                 MissionStatus.COMPLETED, (), "completed",
                                 qa_worker_id="qa-verify-01")
        return MissionResult(mission_id, objective, "software-manager",
                             MissionStatus.BLOCKED, (), self.reason)

    def _record(self, mission_id, owner, result):
        if result.status is MissionStatus.COMPLETED:
            self.queue.complete(mission_id, owner=owner, result=result)
        else:
            self.queue.block(mission_id, owner=owner, result=result)


@pytest.mark.parametrize("reason,cause", CASES)
def test_failure_fix_verify_chain(tmp_path, reason, cause):
    queue = PersistentMissionQueue(tmp_path / "company-service.db")
    worker = "software-manager"
    profile = cm.load(tmp_path, worker, "software")
    cm.learn_procedural(profile, plan_type="executor", ok=True)  # eski güvenilir yöntem
    cm.save(tmp_path, profile)

    # 1) hata
    queue.enqueue(mission_id="fix-1", objective="test görevi",
                  primary_department="software")
    report = drain(Console(tmp_path, queue, reason), limit=1)
    assert report["executed"] == ["fix-1"]
    mission = queue.get("fix-1")
    assert mission.status is QueueStatus.BLOCKED
    assert cm.classify_cause(reason) == cause

    cm.record_episode(profile, mission_id="fix-1", outcome="blocked",
                      summary=reason, evidence_ok=True, plan_type="executor")
    failed = cm.reflect(profile, mission_id="fix-1", ok=False, reason=reason,
                        plan_type="executor", evidence_ok=True)
    assert cause in failed["cause"] or failed["cause"] == cause
    assert "doğrula" in failed["lesson"]

    # 2) yeni yöntem başarısızsa eski tercih korunur
    score_plan(tmp_path, worker, "software", "yeni_yontem", False, 1.0)
    mind = load_mind(tmp_path, worker)
    preferred = mind.self_model.get("best_plan_type")
    assert preferred == "executor", preferred

    # 3) düzeltme + yeniden çalıştırma
    queue.enqueue(mission_id="fix-1", objective="test görevi",
                  primary_department="software", replace_existing=True)
    fixed = drain(Console(tmp_path, queue, reason, success=True), limit=1)
    assert fixed["executed"] == ["fix-1"]
    assert queue.get("fix-1").status is QueueStatus.COMPLETED

    # 4) doğrulanmış ders + prosedürel hafızada iki sonuç da durur
    profile = cm.load(tmp_path, worker, "software")
    verified = cm.reflect(profile, mission_id="fix-1", ok=True, plan_type="executor",
                          evidence_ok=True)
    assert "doğrulandı" in verified["lesson"]
    cm.learn_procedural(profile, plan_type="executor", ok=False)
    cm.save(tmp_path, profile)
    row = cm.load(tmp_path, worker)["memory"]["procedural"][0]
    assert row["ok"] >= 1 and row["fail"] >= 1
