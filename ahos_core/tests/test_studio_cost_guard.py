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


def test_estimate_math_and_stage_breakdown():
    """Tahmin: units * price; stage bazında toplanır; para birimi katalogdan."""

    from ahos.costs import estimate

    report = estimate([
        {"stage": "voice", "provider": "local-edge", "units": 12.0},
        {"stage": "video", "provider": "runpod-video", "units": 10.0},
        {"stage": "video", "provider": "runpod-video", "units": 5.0},
    ])
    assert report["currency"] == "USD"
    assert report["stages"]["voice"]["cost"] == 0.0
    assert report["stages"]["video"]["cost"] == round(15.0 * 0.012, 4)
    assert report["total_cost"] == round(15.0 * 0.012, 4)
    assert report["paid_providers"] == ["runpod-video"]


def test_budget_refusal_happens_before_calls():
    """Bütçe aşımı `BudgetRefusal` ile reddedilir (çağrı yapılmaz)."""

    import pytest

    from ahos.costs import BudgetRefusal, estimate, guard

    report = estimate([{"stage": "video", "provider": "runpod-video", "units": 100.0}])
    assert report["total_cost"] > 1.0
    with pytest.raises(BudgetRefusal):
        guard(report, episode_cap=0.5)
    with pytest.raises(BudgetRefusal):
        guard(report, episode_cap=100.0, provider_caps={"runpod-video": 0.5})
    assert guard(report, episode_cap=100.0)["ok"] is True


def test_free_first_ordering_prefers_local():
    """Ücretsiz/yerel sağlayıcı her zaman önce; ücretli sonra."""

    from ahos.costs import order_providers

    ordered = order_providers(["runpod-voice", "local-edge", "runpod-kokoro"],
                              approval="owner-ok")
    assert ordered[0]["provider_id"] == "local-edge"
    assert ordered[0]["paid"] is False
    assert all(row["paid"] for row in ordered[1:])


def test_paid_provider_requires_approval_token():
    """Approval token yoksa ücretli sağlayıcı sıralamaya hiç girmez."""

    from ahos.costs import order_providers

    ordered = order_providers(["runpod-voice", "local-edge"])
    assert [row["provider_id"] for row in ordered] == ["local-edge"]

    with_token = order_providers(["runpod-voice"], approval="owner-ok")
    assert [row["provider_id"] for row in with_token] == ["runpod-voice"]


def test_ledger_breakdown_and_blocked_evidence(tmp_path):
    """Bitmiş bölüm: stage bazında maliyet + blocked_budget evidence dosyası."""

    import json

    from ahos.costs import CostLedger

    ledger = CostLedger()
    ledger.charge("voice", "local-edge", units=10.0, cost=0.0)
    ledger.charge("video", "runpod-video", units=5.0, cost=0.06)
    breakdown = ledger.breakdown()
    assert breakdown["stages"] == {"voice": 0.0, "video": 0.06}
    assert breakdown["total_cost"] == 0.06

    path = ledger.write_evidence(tmp_path / "cost-evidence.json", blocked=True,
                                 reason="episode cap")
    payload = json.loads((tmp_path / "cost-evidence.json").read_text(encoding="utf-8"))
    assert payload["blocked_budget"] is True and payload["reason"] == "episode cap"
    assert path["total_cost"] == 0.06

