"""V4 G010-G012: uzman yönlendirme, yardımlaşma ve çok-departman projesi."""
from __future__ import annotations

import json
import time

import pytest

from ahos import cognitive_memory as cm
from ahos import expert_router, help_workflow, project_run


def _write_departments(runtime, departments):
    (runtime / "departments.json").write_text(
        json.dumps({"departments": departments}), encoding="utf-8")


def _departments():
    return [
        {"department_id": "creative", "workers": [
            {"worker_id": "c-idle", "capabilities": ["storyboard", "screenplay"]},
            {"worker_id": "c-busy", "capabilities": ["storyboard"]},
        ]},
        {"department_id": "software", "workers": [
            {"worker_id": "s-dev", "capabilities": ["python", "testing"]},
        ]},
        {"department_id": "quality", "workers": [
            {"worker_id": "q-qa", "capabilities": ["qa", "verification"]},
        ]},
        {"department_id": "data", "workers": [
            {"worker_id": "d-data", "capabilities": ["sqlite", "analytics"]},
        ]},
    ]


def _setup(tmp_path):
    _write_departments(tmp_path, _departments())
    for worker, plan, ok_count, fail_count in (
            ("c-idle", "storyboard", 4, 0), ("c-busy", "storyboard", 1, 3),
            ("s-dev", "python", 5, 0), ("q-qa", "qa", 4, 1), ("d-data", "sqlite", 3, 0)):
        profile = cm.load(tmp_path, worker)
        for index in range(ok_count):
            cm.learn_procedural(profile, plan_type=plan, ok=True)
        for index in range(fail_count):
            cm.learn_procedural(profile, plan_type=plan, ok=False)
        cm.save(tmp_path, profile)
    # c-busy son 10 dk içinde görev yaptı → meşgul
    minds = tmp_path / "minds"
    minds.mkdir(exist_ok=True)
    (minds / "c-busy.json").write_text(json.dumps({
        "worker_id": "c-busy", "department": "creative",
        "events": [{"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "kind": "mission", "ok": True}],
        "self_model": {}}), encoding="utf-8")


SCENARIOS = (
    [("python", "creative", "s-dev", True) for _ in range(5)]
    + [("qa", "software", "q-qa", True) for _ in range(5)]
    + [("storyboard", "creative", "c-idle", False) for _ in range(4)]
    + [("sqlite", "data", "d-data", False) for _ in range(3)]
    + [("quantum-tensor", "creative", None, False) for _ in range(3)]
)


def test_twenty_cross_department_routing_scenarios(tmp_path):
    _setup(tmp_path)
    assert len(SCENARIOS) == 20
    for skill, department, expected, cross in SCENARIOS:
        result = expert_router.route(tmp_path, [skill], department=department)
        if expected is None:
            assert result["selected"] is None
            continue
        assert result["selected"]["worker"] == expected, (skill, department, result)
        assert result["cross_department"] is cross, (skill, department, result)
        assert result["rationale"]
    log = (tmp_path / "cognition" / "_routing.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(log) == 20


def test_routing_prefers_idle_worker_with_evidence(tmp_path):
    _setup(tmp_path)
    result = expert_router.route(tmp_path, ["storyboard"], department="creative")
    assert result["selected"]["worker"] == "c-idle"
    assert result["selected"]["busy"] is False
    assert result["selected"]["rate"] == 1.0


def test_ten_real_help_cases_are_qa_verified(tmp_path):
    for index in range(10):
        request = help_workflow.open_request(
            tmp_path, mission_id=f"m-{index}", from_worker=f"asker-{index}",
            skill="python", evidence="hata metni")
        request_id = request["request_id"]
        help_workflow.propose(tmp_path, request_id, helper="s-dev",
                              solution=f"testleri izole çalıştır (vaka {index})",
                              expected_result="geçer")
        with pytest.raises(PermissionError):
            help_workflow.verify(tmp_path, request_id, verifier="s-dev", ok=True,
                                 note="kendi çözümü", evidence_ok=True)
        help_workflow.verify(tmp_path, request_id, verifier="q-qa", ok=True,
                             note="bağımsız QA geçti", evidence_ok=True)
        assert help_workflow.status(tmp_path, request_id)["state"] == "verified"

    stats = help_workflow.stats(tmp_path)
    assert stats["verified"] == 10 and stats["requests"] == 10
    shared = [json.loads(line) for line in
              (tmp_path / "cognition" / "_shared.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(shared) == 10 and all(row["verified"] for row in shared)


def test_help_requires_independence_and_evidence(tmp_path):
    request = help_workflow.open_request(tmp_path, mission_id="m-x",
                                         from_worker="asker", skill="qa")
    with pytest.raises(PermissionError):
        help_workflow.propose(tmp_path, request["request_id"], helper="asker",
                              solution="kendim")
    help_workflow.propose(tmp_path, request["request_id"], helper="helper",
                          solution="düzeltme")
    with pytest.raises(ValueError):
        help_workflow.verify(tmp_path, request["request_id"], verifier="qa-01",
                             ok=True, note="kanıtsız", evidence_ok=False)
    help_workflow.verify(tmp_path, request["request_id"], verifier="qa-01",
                         ok=False, note="test geçmedi", evidence_ok=True)
    assert help_workflow.status(tmp_path, request["request_id"])["state"] == "rejected"
    assert not (tmp_path / "cognition" / "_shared.jsonl").exists()


def _project_tasks():
    return [
        {"task_id": "script", "department": "creative", "objective": "senaryo"},
        {"task_id": "build", "department": "software", "objective": "uygulama",
         "depends_on": ["script"]},
        {"task_id": "verify", "department": "quality", "objective": "kabul",
         "depends_on": ["build"]},
    ]


def test_cross_department_project_delivered_end_to_end(tmp_path):
    outputs = {}

    def executor(task):
        outputs[task["task_id"]] = f"{task['department']}:{task['task_id']}:ok"
        return {"ok": True, "output": outputs[task["task_id"]],
                "evidence": "evidence.md", "worker": f"{task['department']}-worker"}

    def qa(task, result):
        return {"ok": result["output"].endswith(":ok"),
                "verifier": "independent-qa", "note": "bağımsız doğrulama"}

    state = project_run.run_project(tmp_path, project_id="proj-1", manager="ceo-01",
                                    tasks=_project_tasks(), executor=executor, qa=qa)
    assert state["delivered"] is True
    assert state["summary"]["completed"] == 3
    assert all(row["verifier"] == "independent-qa" for row in state["tasks"])
    saved = json.loads((tmp_path / "projects" / "proj-1" / "state.json").read_text(encoding="utf-8"))
    assert saved["delivered"] is True


def test_project_qa_failure_blocks_dependents(tmp_path):
    def executor(task):
        return {"ok": True, "output": "done", "evidence": "e", "worker": "w-1"}

    def qa(task, result):
        if task["task_id"] == "build":
            return {"ok": False, "verifier": "qa-01", "note": "kabul testi düştü"}
        return {"ok": True, "verifier": "qa-01", "note": "geçti"}

    state = project_run.run_project(tmp_path, project_id="proj-2", manager="ceo-01",
                                    tasks=_project_tasks(), executor=executor, qa=qa)
    assert state["delivered"] is False
    statuses = {row["task_id"]: row["status"] for row in state["tasks"]}
    assert statuses["script"] == "completed"
    assert statuses["build"] == "qa_failed"
    assert statuses["verify"] == "blocked"


def test_project_dependency_cycle_rejected(tmp_path):
    tasks = [
        {"task_id": "a", "department": "creative", "objective": "a", "depends_on": ["b"]},
        {"task_id": "b", "department": "software", "objective": "b", "depends_on": ["a"]},
    ]
    with pytest.raises(ValueError):
        project_run.run_project(tmp_path, project_id="proj-3", manager="ceo-01",
                                tasks=tasks, executor=lambda task: {"ok": True},
                                qa=lambda task, result: {"ok": True, "verifier": "qa"})
