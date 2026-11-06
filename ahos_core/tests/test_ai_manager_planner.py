from __future__ import annotations

import json
from pathlib import Path

import pytest

from ahos.ai_manager_planner import OpenHandsManagerPlanner


def _write_plan(workspace: Path, payload: dict) -> None:
    (workspace / "MISSION_PLAN.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )


def test_valid_plan_is_parsed_and_owner_approval_is_never_self_granted(
    tmp_path: Path,
) -> None:
    def runner(_prompt: str, workspace: Path):
        _write_plan(
            workspace,
            {
                "steps": [
                    {
                        "step_id": "research",
                        "title": "Research requirements",
                        "department": "research",
                        "required_capabilities": ["research"],
                        "depends_on": [],
                        "estimated_cost_usd": 0.0,
                        "owner_approved": True,
                    },
                    {
                        "step_id": "build",
                        "title": "Build prototype",
                        "department": "software",
                        "required_capabilities": ["python"],
                        "depends_on": ["research"],
                        "estimated_cost_usd": 0.0,
                    },
                ]
            },
        )

    planner = OpenHandsManagerPlanner(
        runner=runner,
        workspace_root=tmp_path,
        allowed_departments=frozenset({"research", "software"}),
        max_steps=4,
        max_total_estimated_cost_usd=0.0,
    )

    steps = tuple(planner("m1", "objective", "mgr-software-01"))

    assert [s.department for s in steps] == ["research", "software"]
    assert steps[1].depends_on == ("research",)
    assert all(s.owner_approved is False for s in steps)


def test_disallowed_department_is_rejected(tmp_path: Path) -> None:
    def runner(_prompt: str, workspace: Path):
        _write_plan(
            workspace,
            {
                "steps": [
                    {
                        "step_id": "sales",
                        "title": "Contact customer",
                        "department": "sales",
                        "required_capabilities": ["sales"],
                        "depends_on": [],
                    }
                ]
            },
        )

    planner = OpenHandsManagerPlanner(
        runner=runner,
        workspace_root=tmp_path,
        allowed_departments=frozenset({"research", "software"}),
    )

    with pytest.raises(ValueError, match="disallowed department"):
        tuple(planner("m2", "objective", "mgr-software-01"))


def test_cost_limit_is_enforced(tmp_path: Path) -> None:
    def runner(_prompt: str, workspace: Path):
        _write_plan(
            workspace,
            {
                "steps": [
                    {
                        "step_id": "build",
                        "title": "Build",
                        "department": "software",
                        "required_capabilities": ["python"],
                        "depends_on": [],
                        "estimated_cost_usd": 0.01,
                    }
                ]
            },
        )

    planner = OpenHandsManagerPlanner(
        runner=runner,
        workspace_root=tmp_path,
        allowed_departments=frozenset({"software"}),
        max_total_estimated_cost_usd=0.0,
    )

    with pytest.raises(ValueError, match="cost limit"):
        tuple(planner("m3", "objective", "mgr-software-01"))


def test_missing_plan_file_is_rejected(tmp_path: Path) -> None:
    planner = OpenHandsManagerPlanner(
        runner=lambda _prompt, _workspace: None,
        workspace_root=tmp_path,
        allowed_departments=frozenset({"software"}),
    )

    with pytest.raises(ValueError, match="did not create"):
        tuple(planner("m4", "objective", "mgr-software-01"))
