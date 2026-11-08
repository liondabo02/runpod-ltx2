"""Canlı LLM yürütme noktasında Studio-16 token koruması."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from ahos.llm_executor import ModelError, _studio_budget_preflight


def _settings(max_tokens: int = 100) -> SimpleNamespace:
    return SimpleNamespace(max_tokens=max_tokens)


def test_small_prompt_passes():
    _studio_budget_preflight("sistem", "küçük görev", _settings())


def test_large_prompt_is_blocked_before_http():
    with pytest.raises(ModelError, match="bütçe"):
        _studio_budget_preflight("x" * 60000, "y" * 60000, _settings())


def test_guard_can_be_disabled_with_env(monkeypatch):
    monkeypatch.setenv("AHOS_STUDIO_COST_GUARD", "0")
    _studio_budget_preflight("x" * 60000, "y" * 60000, _settings())
