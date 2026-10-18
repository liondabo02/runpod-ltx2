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


def test_capability_catalog_accepts_exact_routable_capabilities(
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
        capability_catalog={
            "research": frozenset({"research", "analysis"}),
            "software": frozenset({"python", "automation"}),
        },
        max_steps=4,
        max_total_estimated_cost_usd=0.0,
    )

    steps = tuple(planner("m1", "objective", "mgr-software-01"))

    assert steps[0].required_capabilities == frozenset({"research"})
    assert steps[1].required_capabilities == frozenset({"python"})


def test_invented_capability_is_rejected(tmp_path: Path) -> None:
    def runner(_prompt: str, workspace: Path):
        _write_plan(
            workspace,
            {
                "steps": [
                    {
                        "step_id": "research",
                        "title": "Research",
                        "department": "research",
                        "required_capabilities": ["requirements_analysis"],
                        "depends_on": [],
                        "estimated_cost_usd": 0.0,
                    }
                ]
            },
        )

    planner = OpenHandsManagerPlanner(
        runner=runner,
        workspace_root=tmp_path,
        allowed_departments=frozenset({"research"}),
        capability_catalog={
            "research": frozenset({"research", "analysis"}),
        },
        max_total_estimated_cost_usd=0.0,
    )

    with pytest.raises(ValueError, match="unroutable capabilities"):
        tuple(planner("m2", "objective", "mgr-software-01"))


def test_owner_approval_is_never_self_granted(tmp_path: Path) -> None:
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
                        "estimated_cost_usd": 0.0,
                        "owner_approved": True,
                    }
                ]
            },
        )

    planner = OpenHandsManagerPlanner(
        runner=runner,
        workspace_root=tmp_path,
        allowed_departments=frozenset({"software"}),
        capability_catalog={
            "software": frozenset({"python"}),
        },
        max_total_estimated_cost_usd=0.0,
    )

    steps = tuple(planner("m3", "objective", "mgr-software-01"))
    assert steps[0].owner_approved is False


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
        capability_catalog={
            "software": frozenset({"python"}),
        },
        max_total_estimated_cost_usd=0.0,
    )

    with pytest.raises(ValueError, match="cost limit"):
        tuple(planner("m4", "objective", "mgr-software-01"))
