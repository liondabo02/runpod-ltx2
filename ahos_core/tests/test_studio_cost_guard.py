"""Stüdyo maliyet/döngü koruması testleri."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ahos.studio_cost_guard import (BudgetExceeded, LoopGuard, Policy, authorize, charge,
                                    estimate_tokens, guard_attempts, load_policy)

ROOT = Path(__file__).resolve().parents[2]


def test_deterministic_tasks_do_not_use_llm():
    result = authorize("deterministic", pending=0, cached=False, owner_approval=False)
    assert result == {"allowed": False, "reason": "deterministic_local_only", "model": None}


def test_cache_hit_prevents_duplicate_research():
    result = authorize("standard", pending=0, cached=True, owner_approval=False)
    assert result["allowed"] is False and result["reason"] == "cache_hit"


def test_pending_cap_blocks_new_work():
    result = authorize("standard", pending=301, cached=False, owner_approval=False)
    assert result["allowed"] is False and result["reason"] == "pending_cap_exceeded"


def test_paid_requires_owner_approval():
    denied = authorize("paid", pending=0, cached=False, owner_approval=False)
    allowed = authorize("paid", pending=0, cached=False, owner_approval=True)
    assert denied["allowed"] is False and denied["reason"] == "paid_requires_owner_approval"
    assert allowed["allowed"] is True and allowed["model"] == "remote-paid"


def test_token_and_cost_limits_stop_the_task():
    with pytest.raises(BudgetExceeded):
        charge(20000, 0.0)
    with pytest.raises(BudgetExceeded):
        charge(100, 1.0)


def test_loop_guard_stops_retries():
    assert guard_attempts(2) == 2
    with pytest.raises(LoopGuard):
        guard_attempts(3)


def test_policy_file_is_zero_cost_and_cheap_first():
    policy = load_policy(ROOT / "studio" / "production" / "cost-policy.json")
    assert policy.max_cost_usd == 0.0
    assert policy.pending_cap == 300
    assert policy.cheap_first is True
    assert estimate_tokens("abcd" * 100) == 100
    assert Policy().max_retries == 2
