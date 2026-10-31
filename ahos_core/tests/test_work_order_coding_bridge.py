import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from ahos.coding_supervisor import CodingSupervisorStore, CodingTaskStatus
from ahos.work_order import WorkOrderStatus, WorkOrderStore
from ahos.work_order_coding_bridge import CodingBridgeError, CodingWorkContract, WorkOrderCodingBridge


def repo(path: Path) -> Path:
    path.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    return path


def contract_file(tmp_path: Path, repository: Path) -> Path:
    path = tmp_path / "contract.json"
    path.write_text(json.dumps({
        "schema": "ahos.coding-work-contract.v1", "work_order_id": "wo-1",
        "title": "Implement safe feature", "repository": str(repository),
        "allowed_paths": ["ahos_core/ahos"],
        "test_commands": [["python", "-m", "pytest", "-q"]], "max_attempts": 2,
    }), encoding="utf-8")
    return path


def order_store(tmp_path: Path, *, department: str = "software") -> WorkOrderStore:
    store = WorkOrderStore(tmp_path / "orders.json")
    store.create(work_order_id="wo-1", venture_id="v", mission_id="m",
                 capability_requirements=("coding",), priority=7,
                 routing_department=department)
    store.transition("wo-1", WorkOrderStatus.READY)
    return store


def test_ready_software_order_is_dispatched_idempotently(tmp_path: Path):
    work = order_store(tmp_path)
    coding = CodingSupervisorStore(tmp_path / "coding.json")
    contract = CodingWorkContract.from_json(contract_file(tmp_path, repo(tmp_path / "repo")))
    bridge = WorkOrderCodingBridge(work, coding)
    first = bridge.dispatch(contract)
    second = bridge.dispatch(contract)
    assert first == second
    assert first.status is CodingTaskStatus.QUEUED
    assert first.priority == 7
    assert work.get("wo-1").status is WorkOrderStatus.IN_PROGRESS
    assert len(coding.all()) == 1


def test_non_software_order_is_rejected(tmp_path: Path):
    bridge = WorkOrderCodingBridge(order_store(tmp_path, department="creative"),
                                   CodingSupervisorStore(tmp_path / "coding.json"))
    contract = CodingWorkContract.from_json(contract_file(tmp_path, repo(tmp_path / "repo")))
    with pytest.raises(CodingBridgeError, match="software"):
        bridge.dispatch(contract)



def _owner_reviewed_patch(tmp_path: Path, coding: CodingSupervisorStore, task_id: str, *, approved: bool):
    claimed = coding.claim("dev-01")
    assert claimed is not None and claimed.task_id == task_id
    patch = tmp_path / "candidate.patch"
    patch.write_bytes(b"diff --git a/a.py b/a.py\n+fixed\n")
    approval = tmp_path / "approval.json"
    approval.write_text(json.dumps({
        "patch_sha256": hashlib.sha256(patch.read_bytes()).hexdigest()
    }), encoding="utf-8")
    coding.finish(task_id, "dev-01", success=True, reason="tests passed",
                  patch_file=patch, approval_file=approval)
    return patch, approval


def test_ceo_work_order_waits_for_owner_and_then_reconciles(tmp_path: Path):
    work = order_store(tmp_path)
    coding = CodingSupervisorStore(tmp_path / "coding.json")
    bridge = WorkOrderCodingBridge(work, coding)
    record = bridge.dispatch(CodingWorkContract.from_json(contract_file(
        tmp_path, repo(tmp_path / "repo"))))

    patch, approval = _owner_reviewed_patch(tmp_path, coding, record.task_id, approved=True)
    assert bridge.reconcile() == ()
    assert work.get("wo-1").status is WorkOrderStatus.IN_PROGRESS

    coding.record_owner_decision(record.task_id, approved=True)
    changed = bridge.reconcile()
    assert len(changed) == 1 and changed[0].status is WorkOrderStatus.COMPLETED
    assert bridge.reconcile() == ()


def test_rejected_coding_task_marks_work_order_failed(tmp_path: Path):
    work = order_store(tmp_path)
    coding = CodingSupervisorStore(tmp_path / "coding.json")
    bridge = WorkOrderCodingBridge(work, coding)
    record = bridge.dispatch(CodingWorkContract.from_json(contract_file(
        tmp_path, repo(tmp_path / "repo"))))
    _owner_reviewed_patch(tmp_path, coding, record.task_id, approved=False)
    coding.record_owner_decision(record.task_id, approved=False)
    assert bridge.reconcile()[0].status is WorkOrderStatus.FAILED


def test_tampered_patch_is_not_reported_to_ceo_as_completed(tmp_path: Path):
    work = order_store(tmp_path)
    coding = CodingSupervisorStore(tmp_path / "coding.json")
    bridge = WorkOrderCodingBridge(work, coding)
    record = bridge.dispatch(CodingWorkContract.from_json(contract_file(
        tmp_path, repo(tmp_path / "repo"))))
    patch, _ = _owner_reviewed_patch(tmp_path, coding, record.task_id, approved=True)
    coding.record_owner_decision(record.task_id, approved=True)
    patch.write_text("tampered after approval", encoding="utf-8")
    with pytest.raises(CodingBridgeError, match="modified"):
        bridge.reconcile()
    assert work.get("wo-1").status is WorkOrderStatus.IN_PROGRESS


def test_missing_repository_contract_fails_closed(tmp_path: Path):
    source = contract_file(tmp_path, repo(tmp_path / "repo"))
    payload = json.loads(source.read_text(encoding="utf-8"))
    del payload["repository"]
    source.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(CodingBridgeError, match="repository must be explicitly"):
        CodingWorkContract.from_json(source)


@pytest.mark.parametrize("path", ["", ".", "../private"])
def test_unsafe_or_unscoped_software_contract_rejected(tmp_path: Path, path: str):
    source = contract_file(tmp_path, repo(tmp_path / "repo"))
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["allowed_paths"] = [path]
    source.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(CodingBridgeError, match="unsafe allowed path"):
        CodingWorkContract.from_json(source)


def test_coding_task_requires_acceptance_tests(tmp_path: Path):
    source = contract_file(tmp_path, repo(tmp_path / "repo"))
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["test_commands"] = []
    source.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(CodingBridgeError, match="acceptance test command"):
        CodingWorkContract.from_json(source)
