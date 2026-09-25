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

