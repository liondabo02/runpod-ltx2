"""G017 testleri: 30 görev tipi, ücretli kapı, bağımsız QA."""
from __future__ import annotations

import pytest

from ahos import task_routing


def test_exactly_thirty_task_types_route_to_known_classes():
    assert len(task_routing.TASK_TYPES) == 30
    rows = task_routing.report()
    assert len(rows) == 30
    classes = {row["route"] for row in rows}
    assert classes <= {"deterministic", "local_light", "strong_model", "code_model",
                       "vision", "video", "research", "qa"}
    assert all(row["reason"] for row in rows)


def test_deterministic_never_calls_model():
    for task_type in ("simple_edit", "file_check", "status_report", "health_check"):
        row = task_routing.route(task_type)
        assert row["route"] == "deterministic"
        assert row["model"] == "python" and row["paid"] is False


def test_paid_route_requires_explicit_allow_and_budget(monkeypatch):
    monkeypatch.setenv("AHOS_ALLOW_PAID_LLM", "0")
    blocked = task_routing.route("architecture_review")
    assert blocked["paid"] is False
    assert "ücretsiz yedek" in blocked["reason"]

    monkeypatch.setenv("AHOS_ALLOW_PAID_LLM", "1")
    no_budget = task_routing.route("architecture_review", budget_usd=0)
    assert no_budget["paid"] is False
    allowed = task_routing.route("architecture_review", budget_usd=0.02)
    assert allowed["paid"] is True and allowed["model"]


def test_qa_is_always_independent_and_unpaid():
    row = task_routing.route("independent_qa", budget_usd=1.0, paid_allowed=True)
    assert row["qa_independent"] is True
    assert row["paid"] is False
    assert row["route"] == "qa"


def test_unknown_task_type_is_unrouted():
    row = task_routing.route("bilinmeyen-is")
    assert row["route"] == "unrouted" and row["model"] is None


def test_all_classes_have_a_model_or_tool():
    for row in task_routing.report(budget_usd=0.0):
        assert row["route"] == "unrouted" or row["model"]
