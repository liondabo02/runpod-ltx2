"""Paid model falls back to the cloud VM's free local model."""

from __future__ import annotations

from ahos.llm_executor import ModelSettings, _fallback_settings


def _settings(**overrides) -> ModelSettings:
    base = dict(
        base_url="https://openrouter.ai/api/v1",
        api_key="paid",
        model="openai/gpt-4o-mini",
        max_usd_per_run=0.02,
        input_usd_per_1k=0.0,
        output_usd_per_1k=0.0,
        timeout_seconds=120.0,
        max_files=3,
        max_bytes=200_000,
        browser_check=False,
        max_tokens=4096,
        fallback_models=(),
    )
    base.update(overrides)
    return ModelSettings(**base)


def test_fallback_points_to_the_local_vm(monkeypatch) -> None:
    monkeypatch.setenv("AHOS_FALLBACK_BASE_URL", "http://127.0.0.1:11500/v1")
    monkeypatch.setenv("AHOS_FALLBACK_MODEL", "qwen2.5-coder:3b")
    monkeypatch.setenv("AHOS_FALLBACK_TIMEOUT", "600")

    fallback = _fallback_settings(_settings())

    assert fallback is not None
    assert fallback.base_url.endswith("11500/v1")
    assert fallback.model == "qwen2.5-coder:3b"
    assert fallback.timeout_seconds == 600.0
    assert fallback.max_usd_per_run == 0.0 or fallback.model.startswith("qwen")


def test_no_fallback_when_not_configured(monkeypatch) -> None:
    for name in ("AHOS_FALLBACK_BASE_URL", "AHOS_FALLBACK_MODEL"):
        monkeypatch.delenv(name, raising=False)

    assert _fallback_settings(_settings()) is None


def test_fallback_never_points_to_the_same_endpoint(monkeypatch) -> None:
    monkeypatch.setenv("AHOS_FALLBACK_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("AHOS_FALLBACK_MODEL", "some-model")

    assert _fallback_settings(_settings()) is None
