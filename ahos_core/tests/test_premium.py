from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from ahos import premium


def test_disabled_when_paid_not_allowed(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AHOS_ALLOW_PAID_LLM", "0")

    with pytest.raises(premium.PremiumUnavailable):
        premium.call_premium("sys", "user", tmp_path)


def test_missing_key_is_unavailable(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AHOS_ALLOW_PAID_LLM", "1")
    monkeypatch.setenv("AHOS_PREMIUM_ENABLED", "1")
    monkeypatch.delenv("AHOS_PREMIUM_API_KEY", raising=False)
    monkeypatch.delenv("AHOS_LLM_API_KEY", raising=False)

    with pytest.raises(premium.PremiumUnavailable):
        premium.call_premium("sys", "user", tmp_path)


def test_budget_exceeded(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AHOS_ALLOW_PAID_LLM", "1")
    monkeypatch.setenv("AHOS_PREMIUM_API_KEY", "test-key")
    monkeypatch.setenv("AHOS_PREMIUM_DAILY_USD", "0.01")
    (tmp_path / "premium-spend.jsonl").write_text(
        json.dumps({"day": premium.time.strftime("%Y-%m-%d"), "cost_usd": 0.01}) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(premium.PremiumBudgetExceeded):
        premium.call_premium("sys", "user", tmp_path)


def test_successful_call_records_cost(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AHOS_ALLOW_PAID_LLM", "1")
    monkeypatch.setenv("AHOS_PREMIUM_API_KEY", "test-key")
    monkeypatch.setenv("AHOS_PREMIUM_DAILY_USD", "1.00")

    def fake_transport(model, key, system, prompt, max_tokens):
        return {
            "choices": [{"message": {"content": "OK", "reasoning": None}}],
            "usage": {"cost": 0.002, "total_tokens": 120},
        }

    result = premium.call_premium("sys", "user", tmp_path, transport=fake_transport)

    assert result.text == "OK"
    assert result.cost_usd == 0.002
    assert premium.spent_today(tmp_path) == 0.002


def test_reasoning_fallback_when_content_empty(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AHOS_ALLOW_PAID_LLM", "1")
    monkeypatch.setenv("AHOS_PREMIUM_API_KEY", "test-key")

    def fake_transport(model, key, system, prompt, max_tokens):
        return {
            "choices": [{"message": {"content": None, "reasoning": "düşünce metni"}}],
            "usage": {"cost": 0.001, "total_tokens": 30},
        }

    result = premium.call_premium("sys", "user", tmp_path, transport=fake_transport)

    assert result.text == "düşünce metni"


def test_empty_response_is_unavailable(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AHOS_ALLOW_PAID_LLM", "1")
    monkeypatch.setenv("AHOS_PREMIUM_API_KEY", "test-key")

    def fake_transport(model, key, system, prompt, max_tokens):
        return {"choices": [{"message": {"content": "", "reasoning": ""}}], "usage": {}}

    with pytest.raises(premium.PremiumUnavailable):
        premium.call_premium("sys", "user", tmp_path, transport=fake_transport)


def test_spent_today_ignores_other_days(tmp_path) -> None:
    (tmp_path / "premium-spend.jsonl").write_text(
        json.dumps({"day": "2000-01-01", "cost_usd": 5.0}) + "\n"
        + json.dumps({"day": premium.time.strftime("%Y-%m-%d"), "cost_usd": 0.25}) + "\n",
        encoding="utf-8",
    )

    assert premium.spent_today(tmp_path) == 0.25
