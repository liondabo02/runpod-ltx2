import os

import pytest

from ahos.studio_provider_handlers import (
    ProductionProviderConfig,
    StudioProviderConfigurationError,
)


def test_provider_config_fails_closed_when_secrets_or_budget_are_missing(monkeypatch):
    for name in (
        "RUNPOD_API_KEY", "KURDISH_TTS_API_KEY", "RUNPOD_LTX2_ENDPOINT_ID",
        "RUNPOD_CHATTERBOX_ENDPOINT_ID", "AHOS_RENDER_COST_CEILING_USD",
        "AHOS_TTS_COST_CEILING_USD",
    ):
        monkeypatch.delenv(name, raising=False)
    config = ProductionProviderConfig.from_environment()
    with pytest.raises(StudioProviderConfigurationError, match="not ready"):
        config.validate()
    assert config.status()["runpod_api_key_present"] is False


def test_provider_config_reads_only_secret_presence(monkeypatch):
    monkeypatch.setenv("RUNPOD_API_KEY", "super-secret")
    monkeypatch.setenv("KURDISH_TTS_API_KEY", "also-secret")
    monkeypatch.setenv("RUNPOD_LTX2_ENDPOINT_ID", "ltx")
    monkeypatch.setenv("RUNPOD_CHATTERBOX_ENDPOINT_ID", "tts")
    monkeypatch.setenv("AHOS_RENDER_COST_CEILING_USD", "1.25")
    monkeypatch.setenv("AHOS_TTS_COST_CEILING_USD", "0.75")
    config = ProductionProviderConfig.from_environment()
    config.validate()
    status = config.status()
    assert status["runpod_api_key_present"] is True
    assert "super-secret" not in repr(status)
    assert config.render_cost_ceiling_usd == 1.25


def test_provider_config_rejects_invalid_money(monkeypatch):
    monkeypatch.setenv("AHOS_RENDER_COST_CEILING_USD", "many")
    with pytest.raises(StudioProviderConfigurationError, match="must be numeric"):
        ProductionProviderConfig.from_environment()
