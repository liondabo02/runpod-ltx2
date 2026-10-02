import json
from pathlib import Path

import pytest

from ahos.studio_approval import _hash
from ahos.studio_executor import STAGES, StageResult, StudioExecutionError, StudioExecutor, execution_status


def studio(tmp_path: Path, *, budget: float = 5.0, estimate: float = 4.0) -> Path:
    root = tmp_path / "episode"
    root.mkdir()
    decision = {
        "schema": "ahos.owner-decision-receipt.v1", "episode_id": "S01E003",
        "owner_approved": True, "paid_execution_enabled": True,
        "external_execution_enabled": True, "publishing_enabled": False,
        "max_budget_usd": budget,
    }
    decision["decision_hash"] = _hash(decision)
    (root / "OWNER-DECISION.json").write_text(json.dumps(decision), encoding="utf-8")
    (root / "EXECUTION-PREFLIGHT.json").write_text(json.dumps({
        "episode_id": "S01E003", "approval_ready": True,
        "cost_estimate": {"recommended_budget_ceiling": estimate},
    }), encoding="utf-8")
    return root


def handlers(cost: float = 0.5):
    result = {}
    for stage in STAGES:
        def run(root, ledger, name=stage):
            path = root / "runtime-artifacts" / f"{name}.json"
            path.parent.mkdir(exist_ok=True)
            path.write_text(json.dumps({"stage": name}), encoding="utf-8")
            return StageResult((str(path.relative_to(root)),), cost_usd=cost)
        result[stage] = run
    return result


def estimates(value: float = 0.5):
    return {stage: value for stage in STAGES}


def test_executor_resumes_and_stops_at_final_owner_release(tmp_path: Path):
    root = studio(tmp_path)
    executor = StudioExecutor(root, handlers(), stage_cost_estimates=estimates())
    initialized = executor.initialize()
    assert initialized["status"] == "running"
    for index, stage in enumerate(STAGES, start=1):
        ledger = executor.run_once()
        assert ledger["stages"][stage]["status"] == "completed"
        assert ledger["spent_usd"] == index * 0.5
    assert ledger["status"] == "awaiting_final_owner_release"
    assert ledger["publishing_enabled"] is False
    assert execution_status(root)["execution_id"] == initialized["execution_id"]


def test_executor_fails_closed_without_handler_and_does_not_skip_stage(tmp_path: Path):
    root = studio(tmp_path)
    executor = StudioExecutor(root, {})
    executor.initialize()
    ledger = executor.run_once()
    assert ledger["status"] == "blocked"
    assert ledger["stages"]["render"]["status"] == "pending"


def test_executor_rejects_budget_overrun_and_tampered_preflight(tmp_path: Path):
    root = studio(tmp_path, budget=1.0, estimate=0.5)
    executor = StudioExecutor(root, handlers(cost=2.0), stage_cost_estimates=estimates(1.0))
    executor.initialize()
    ledger = executor.run_once()
    assert ledger["status"] == "retryable"
    assert ledger["spent_usd"] == 0
    preflight = root / "EXECUTION-PREFLIGHT.json"
    preflight.write_text(preflight.read_text() + " ", encoding="utf-8")
    with pytest.raises(StudioExecutionError, match="preflight changed"):
        executor.run_once()


def test_executor_requires_owner_gates_and_affordable_preflight(tmp_path: Path):
    root = studio(tmp_path, budget=1.0, estimate=2.0)
    with pytest.raises(StudioExecutionError, match="exceeds owner budget"):
        StudioExecutor(root, handlers(), stage_cost_estimates=estimates()).initialize()
