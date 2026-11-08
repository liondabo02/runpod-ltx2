from __future__ import annotations

from ahos.llm_executor import ModelSettings, _paid_guard


def _settings(**overrides) -> ModelSettings:
    base = dict(
        base_url="http://127.0.0.1:11500/v1",
        api_key="local-only",
        model="qwen2.5-coder:3b",
        max_usd_per_run=0.0,
        input_usd_per_1k=0.0,
        output_usd_per_1k=0.0,
        timeout_seconds=90,
        max_files=3,
        max_bytes=80_000,
        max_tokens=2048,
    )
    base.update(overrides)
    return ModelSettings(**base)


def test_local_tunnel_model_is_allowed(monkeypatch) -> None:
    monkeypatch.delenv("AHOS_ALLOW_PAID_LLM", raising=False)
    assert _paid_guard(_settings()) is None


def test_paid_model_is_blocked_by_default(monkeypatch) -> None:
    monkeypatch.delenv("AHOS_ALLOW_PAID_LLM", raising=False)
    blocked = _paid_guard(
        _settings(base_url="https://api.openai.com/v1", model="openai/gpt-4o-mini")
    )
    assert blocked is not None
    assert "ücretli model" in blocked


def test_paid_host_is_blocked_even_with_local_name(monkeypatch) -> None:
    monkeypatch.delenv("AHOS_ALLOW_PAID_LLM", raising=False)
    blocked = _paid_guard(
        _settings(base_url="https://api.anthropic.com/v1", model="some-model")
    )
    assert blocked is not None


def test_paid_model_allowed_with_explicit_flag(monkeypatch) -> None:
    monkeypatch.setenv("AHOS_ALLOW_PAID_LLM", "1")
    assert (
        _paid_guard(
            _settings(base_url="https://api.openai.com/v1", model="openai/gpt-4o-mini")
        )
        is None
    )


def test_unknown_public_endpoint_is_not_blocked(monkeypatch) -> None:
    """Bilinmeyen host + ücretli görünmeyen model: politika serbest bırakır."""

    monkeypatch.delenv("AHOS_ALLOW_PAID_LLM", raising=False)
    assert (
        _paid_guard(_settings(base_url="https://llm.example.com/v1", model="qwen2.5-coder:3b"))
        is None
    )
