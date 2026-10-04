import json
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from ahos.department_runtime import DepartmentRuntime, DepartmentTask
from ahos.department_structure import CORE_DEPARTMENTS


def draft(prompt):
    request = json.loads(prompt)
    return json.dumps({"title": request["department"], "content": "A detailed original draft responding to the objective, with workflow, responsibilities and explicit review criteria. " * 2,
                       "assumptions": ["This is an unverified draft"], "acceptance_checks": ["Owner reviews the deliverable"]})


def test_all_departments_produce_real_reviewable_artifacts(tmp_path):
    runtime = DepartmentRuntime(tmp_path, draft, max_workers=11)
    for name in CORE_DEPARTMENTS:
        runtime.enqueue(DepartmentTask(name, name, "Prepare department launch deliverable"))
    result = runtime.run_once()
    assert result["counts"] == {"waiting_owner_approval": 11}
    for task in result["tasks"]:
        payload = json.loads((tmp_path / task["artifact"]).read_text())
        assert payload["draft"]["acceptance_checks"]
        assert payload["execution_performed"] is False
    assert result["publishing_enabled"] is False


def test_independent_tasks_overlap_and_dependents_wait(tmp_path):
    barrier = threading.Barrier(2)
    seen = []
    def generate(prompt):
        request = json.loads(prompt)
        seen.append(request)
        if not request["dependency_drafts_untrusted"]:
            barrier.wait(timeout=5)
        return draft(prompt)
    runtime = DepartmentRuntime(tmp_path, generate, max_workers=2)
    runtime.enqueue(DepartmentTask("a", "research", "Research requirements"))
    runtime.enqueue(DepartmentTask("b", "data", "Prepare analysis"))
    runtime.enqueue(DepartmentTask("c", "marketing", "Use research", ("a",)))
    assert runtime.run_once()["counts"] == {"waiting_owner_approval": 2, "queued": 1}
    assert runtime.run_once()["counts"] == {"waiting_owner_approval": 3}
    assert seen[-1]["dependency_drafts_untrusted"][0]["task_id"] == "a"


def test_retry_is_bounded_and_passes_previous_validation_failure(tmp_path):
    prompts = []
    def invalid(prompt):
        prompts.append(json.loads(prompt))
        return '{"title":"Missing content"}'
    runtime = DepartmentRuntime(tmp_path, invalid)
    runtime.enqueue(DepartmentTask("a", "support", "Support draft", max_attempts=2))
    assert runtime.run_once()["tasks"][0]["status"] == "queued"
    assert runtime.run_once()["tasks"][0]["status"] == "retries_exhausted"
    runtime.run_once()
    assert len(prompts) == 2
    assert "content" in prompts[1]["previous_failure"]
    assert not list(tmp_path.glob("department-artifacts/**/*.json"))


def test_provider_missing_blocks_and_can_resume(tmp_path):
    runtime = DepartmentRuntime(tmp_path)
    runtime.enqueue(DepartmentTask("a", "finance", "Prepare budget"))
    record = runtime.run_once()["tasks"][0]
    assert record["status"] == "blocked" and record["attempts"] == 0
    runtime.generator = draft
    assert runtime.run_once()["tasks"][0]["status"] == "waiting_owner_approval"


def test_owner_decision_requires_unchanged_exact_evidence(tmp_path):
    runtime = DepartmentRuntime(tmp_path, draft)
    runtime.enqueue(DepartmentTask("a", "operations", "Prepare workflow"))
    task = runtime.run_once()["tasks"][0]
    with pytest.raises(ValueError, match="evidence"):
        runtime.decide("a", approved=True, evidence_hash="wrong")
    reviewed = runtime.decide("a", approved=True, evidence_hash=task["artifact_hash"])
    assert reviewed["status"] == "owner_approved"
    assert runtime.snapshot()["external_execution_enabled"] is False


def test_tampered_dependency_blocks_consumer(tmp_path):
    runtime = DepartmentRuntime(tmp_path, draft)
    runtime.enqueue(DepartmentTask("a", "research", "Research"))
    task = runtime.run_once()["tasks"][0]
    runtime.enqueue(DepartmentTask("b", "sales", "Proposal", ("a",)))
    (tmp_path / task["artifact"]).write_text("changed")
    task = runtime.run_once()["tasks"][-1]
    assert task["status"] == "blocked"
    assert task["attempts"] == 0


def test_two_schedulers_do_not_duplicate_claims(tmp_path):
    entered = threading.Event()
    release = threading.Event()
    calls = []
    def generate(prompt):
        calls.append(prompt)
        entered.set()
        assert release.wait(5)
        return draft(prompt)
    one = DepartmentRuntime(tmp_path, generate)
    two = DepartmentRuntime(tmp_path, generate)
    one.enqueue(DepartmentTask("a", "creative", "Draft screenplay"))
    with ThreadPoolExecutor(1) as pool:
        future = pool.submit(one.run_once)
        assert entered.wait(5)
        assert two.run_once()["counts"] == {"running": 1}
        release.set()
        future.result()
    assert len(calls) == 1


def test_provider_error_secrets_not_persisted(tmp_path):
    def broken(prompt):
        raise ValueError("sk-secret-credential")
    runtime = DepartmentRuntime(tmp_path, broken)
    runtime.enqueue(DepartmentTask("a", "support", "Support draft", max_attempts=1))
    assert runtime.run_once()["tasks"][0]["last_error"] == "ValueError"
    assert "sk-secret" not in runtime.queue.read_text()


def test_expired_claim_recovered_without_resetting_attempt_limit(tmp_path):
    runtime = DepartmentRuntime(tmp_path, draft)
    runtime.enqueue(DepartmentTask("a", "quality", "Prepare review", max_attempts=1))
    with runtime._lock():
        data = runtime._load()
        data["tasks"]["a"].update(status="running", attempts=1, lease_until=0, claim="old")
        runtime._save(data)
    assert runtime.recover_interrupted() == 1
    task = runtime.snapshot()["tasks"][0]
    assert task["status"] == "retries_exhausted"
    assert task["attempts"] == 1


def test_consumer_cannot_be_approved_after_dependency_rejected(tmp_path):
    runtime = DepartmentRuntime(tmp_path, draft)
    runtime.enqueue(DepartmentTask("a", "research", "Prepare research"))
    upstream = runtime.run_once()["tasks"][0]
    runtime.enqueue(DepartmentTask("b", "marketing", "Prepare campaign", ("a",)))
    downstream = runtime.run_once()["tasks"][-1]
    runtime.decide("a", approved=False, evidence_hash=upstream["artifact_hash"])
    with pytest.raises(ValueError, match="dependency"):
        runtime.decide("b", approved=True, evidence_hash=downstream["artifact_hash"])
