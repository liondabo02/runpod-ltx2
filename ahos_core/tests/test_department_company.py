from pathlib import Path

from ahos.autonomous_company import PersistentMissionQueue, QueueStatus
from ahos.department_company import build_department_company_loop
from ahos.worker_runtime import QaExecutionResult, WorkerExecutionResult


def test_existing_company_mission_routes_to_department_artifact(tmp_path):
    queue = PersistentMissionQueue(tmp_path / "company-service.db")
    queue.enqueue(mission_id="research-draft", objective="Compare requirements",
                  primary_department="research")
    seen = []

    def execute(item, worker_id):
        seen.append((item, worker_id))
        artifact = tmp_path / "draft.md"
        artifact.write_text("Requirements comparison draft")
        return WorkerExecutionResult(item.task_id, worker_id, True,
                                     "Local draft created", (str(artifact),))

    def qa(item, result, worker_id):
        passed = bool(result.artifacts) and all(
            Path(p).is_file() for p in result.artifacts)
        return QaExecutionResult(item.task_id, worker_id, passed, "Artifact checked")

    loop = build_department_company_loop(tmp_path, executors={"research-01": execute},
                                         qa_executor=qa)
    result = loop.run_once()
    assert result.status is QueueStatus.COMPLETED
    assert seen[0][1] == "research-01"
    assert "do not claim the objective has been executed" in seen[0][0].title


def test_unconfigured_department_does_not_claim_completion(tmp_path):
    queue = PersistentMissionQueue(tmp_path / "company-service.db")
    queue.enqueue(mission_id="sales", objective="Create a sales proposal",
                  primary_department="sales")
    loop = build_department_company_loop(tmp_path, executors={}, qa_executor=lambda *_: None)
    result = loop.run_once()
    assert result.status is QueueStatus.BLOCKED
    assert "no draft executor" in result.result_json


def test_persistent_bridge_requires_draft_owner_review(tmp_path):
    import json
    from ahos.department_runtime import DepartmentRuntime
    from ahos.department_company import build_persistent_department_loop, reconcile_department_missions
    generator = lambda _: json.dumps({"title": "Brief", "content": "Concrete proposal with evidence and assumptions. " * 4,
                                       "assumptions": [], "acceptance_checks": ["Review the proposal"]})
    runtime = DepartmentRuntime(tmp_path / "departments", generator)
    queue = PersistentMissionQueue(tmp_path / "company-service.db")
    queue.enqueue(mission_id="draft", objective="draft: Create a research brief", primary_department="research")
    loop = build_persistent_department_loop(tmp_path, runtime)
    assert loop.run_once().status is QueueStatus.WAITING_OWNER_APPROVAL
    task = runtime.snapshot()["tasks"][0]
    runtime.decide(task["task_id"], approved=True, evidence_hash=task["artifact_hash"])
    assert reconcile_department_missions(loop, runtime) == 1
    assert queue.get("draft").status is QueueStatus.COMPLETED


def test_approved_draft_does_not_complete_business_execution(tmp_path):
    import json
    from ahos.department_runtime import DepartmentRuntime
    from ahos.department_company import build_persistent_department_loop, reconcile_department_missions
    generator = lambda _: json.dumps({"title": "Campaign", "content": "Campaign draft for review before external publication. " * 4,
                                       "assumptions": [], "acceptance_checks": ["Review copy"]})
    runtime = DepartmentRuntime(tmp_path / "departments", generator)
    queue = PersistentMissionQueue(tmp_path / "company-service.db")
    queue.enqueue(mission_id="publish", objective="Publish a campaign", primary_department="marketing")
    loop = build_persistent_department_loop(tmp_path, runtime)
    assert loop.run_once().status is QueueStatus.WAITING_OWNER_APPROVAL
    task = runtime.snapshot()["tasks"][0]
    runtime.decide(task["task_id"], approved=True, evidence_hash=task["artifact_hash"])
    assert reconcile_department_missions(loop, runtime) == 0
    assert queue.get("publish").status is QueueStatus.WAITING_OWNER_APPROVAL


def test_busy_draft_queue_does_not_permanently_block_company_mission(tmp_path):
    import json
    from ahos.department_runtime import DepartmentRuntime, DepartmentTask
    from ahos.department_company import build_persistent_department_loop
    runtime = DepartmentRuntime(tmp_path / "departments", lambda _: json.dumps({
        "title": "Draft", "content": "Useful task draft with explicit assumptions. " * 4,
        "assumptions": [], "acceptance_checks": ["Review"]}), max_workers=1)
    for i in range(3):
        runtime.enqueue(DepartmentTask("other-" + str(i), "research", "Research draft"))
    queue = PersistentMissionQueue(tmp_path / "company-service.db")
    queue.enqueue(mission_id="busy", objective="draft: Brief", primary_department="research")
    loop = build_persistent_department_loop(tmp_path, runtime)
    assert loop.run_once().status is QueueStatus.WAITING_OWNER_APPROVAL


def test_reconciliation_blocks_tampered_approved_draft(tmp_path):
    import json
    from ahos.department_runtime import DepartmentRuntime
    from ahos.department_company import build_persistent_department_loop, reconcile_department_missions
    runtime = DepartmentRuntime(tmp_path / "departments", lambda _: json.dumps({
        "title": "Draft", "content": "Useful task draft with explicit assumptions. " * 4,
        "assumptions": [], "acceptance_checks": ["Review"]}))
    queue = PersistentMissionQueue(tmp_path / "company-service.db")
    queue.enqueue(mission_id="tamper", objective="draft: Brief", primary_department="research")
    loop = build_persistent_department_loop(tmp_path, runtime)
    loop.run_once()
    task = runtime.snapshot()["tasks"][0]
    runtime.decide(task["task_id"], approved=True, evidence_hash=task["artifact_hash"])
    (runtime.root / task["artifact"]).write_text("changed")
    reconcile_department_missions(loop, runtime)
    assert queue.get("tamper").status is QueueStatus.BLOCKED


def test_reconciliation_blocks_owner_rejected_draft(tmp_path):
    import json
    from ahos.department_runtime import DepartmentRuntime
    from ahos.department_company import build_persistent_department_loop, reconcile_department_missions
    runtime = DepartmentRuntime(tmp_path / "departments", lambda _: json.dumps({
        "title": "Draft", "content": "Useful task draft with explicit assumptions. " * 4,
        "assumptions": [], "acceptance_checks": ["Review"]}))
    queue = PersistentMissionQueue(tmp_path / "company-service.db")
    queue.enqueue(mission_id="reject", objective="draft: Brief", primary_department="research")
    loop = build_persistent_department_loop(tmp_path, runtime)
    loop.run_once()
    task = runtime.snapshot()["tasks"][0]
    runtime.decide(task["task_id"], approved=False, evidence_hash=task["artifact_hash"])
    reconcile_department_missions(loop, runtime)
    assert queue.get("reject").status is QueueStatus.BLOCKED
