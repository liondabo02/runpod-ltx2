"""Model kayıt defteri: katmanlı seçim ve ücretli kapı."""

from __future__ import annotations

from ahos.model_registry import PROVIDERS, apply, candidates, choose


def test_providers_are_ordered_free_before_paid():
    tiers = [provider.tier for provider in PROVIDERS]
    assert tiers.index("local") < tiers.index("free") < tiers.index("paid")


def test_candidates_skip_paid_unless_allowed(monkeypatch):
    for provider in PROVIDERS:
        monkeypatch.setenv(provider.api_key_env, "test-key")
    monkeypatch.delenv("AHOS_ALLOW_PAID_LLM", raising=False)

    names = [provider.name for provider in candidates("code", probe=False)]
    assert "deepseek" not in names
    assert "nim" in names

    monkeypatch.setenv("AHOS_ALLOW_PAID_LLM", "1")
    names_paid = [provider.name for provider in candidates("code", probe=False)]
    assert "deepseek" in names_paid


def test_local_is_always_a_candidate(monkeypatch):
    for provider in PROVIDERS:
        monkeypatch.delenv(provider.api_key_env, raising=False)
    monkeypatch.delenv("AHOS_ALLOW_PAID_LLM", raising=False)

    names = [provider.name for provider in candidates("code", probe=False)]
    assert names == ["local"]
    chosen = choose("code", probe=False)
    assert chosen is not None and chosen.name == "local"


def test_document_tasks_do_not_need_a_code_model(monkeypatch):
    for provider in PROVIDERS:
        monkeypatch.setenv(provider.api_key_env, "k")
    monkeypatch.delenv("AHOS_ALLOW_PAID_LLM", raising=False)

    names = [provider.name for provider in candidates("document", probe=False)]
    assert "nim" not in names          # nim yalnız kod için tanımlı
    assert "local" in names


def test_apply_writes_executor_variables(monkeypatch):
    monkeypatch.setenv("NVIDIA_NIM_API_KEY", "nvapi-test")
    monkeypatch.delenv("AHOS_ALLOW_PAID_LLM", raising=False)

    provider = next(p for p in PROVIDERS if p.name == "nim")
    result = apply(provider)

    import os

    assert result["has_key"] is True
    assert os.environ["AHOS_LLM_BASE_URL"] == provider.base_url
    assert os.environ["AHOS_LLM_MODEL"] == provider.model
    assert os.environ["AHOS_LLM_API_KEY"] == "nvapi-test"
    assert os.environ["AHOS_LLM_FREE"] == "1"
