"""Cognition planning and simulation contract tests."""
import pytest
from ahos.cognition import plan_from_goal, simulate


def test_simulate_reports_feasible_steps():
    result = simulate("complete a task", ["inspect code", "run tests"], {"blocked": 0})
    assert result["goal"] == "complete a task"
    assert result["feasible"] is True
    assert [s["action"] for s in result["steps"]] == ["inspect code", "run tests"]
    assert all(s["ok"] for s in result["steps"])


def test_simulate_rejects_unnecessary_blocker_cleanup():
    result = simulate("remove blockers", ["engel temizle"], {"blocked": 0})
    assert result["feasible"] is False
    assert result["steps"][0]["ok"] is False


def test_plan_from_goal_is_not_execution_proof():
    plan = plan_from_goal("build a report")
    assert len(plan) == 3
    assert [p["action"].split(":")[0] for p in plan] == ["analyze", "plan", "execute"]
    assert all(p["status"] == "planned" for p in plan)


def test_plan_from_empty_goal_is_rejected():
    with pytest.raises(ValueError, match="boş"):
        plan_from_goal("  ")
