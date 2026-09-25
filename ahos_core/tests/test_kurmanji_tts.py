import struct

import pytest

from ahos.kurmanji_tts import (
    KurdishTTSConfig,
    KurdishTTSExecutionApproval,
    KurdishTTSProvider,
    KurmanjiTTSConfigurationError,
    KurmanjiTTSResponseError,
    KurmanjiTTSUsageError,
    TTSHttpResponse,
    UsageIntent,
    select_kurmanji_provider,
    validate_pcm_wav,
)


def wav(payload=b"\x00\x00"):
    fmt = struct.pack("<4sIHHIIHH", b"fmt ", 16, 1, 1, 24000, 48000, 2, 16)
    data = struct.pack("<4sI", b"data", len(payload)) + payload
    content = b"WAVE" + fmt + data
    return b"RIFF" + struct.pack("<I", len(content)) + content


class Transport:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def synthesize(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


def approval(**overrides):
    values = {
        "owner_approved": True,
        "execution_enabled": True,
        "external_provider_enabled": True,
        "paid_provider_enabled": True,
    }
    values.update(overrides)
    return KurdishTTSExecutionApproval(**values)


def test_mms_is_hard_blocked_for_commercial_publishing():
    with pytest.raises(KurmanjiTTSUsageError, match="evaluation-only"):
        select_kurmanji_provider("meta-mms-kmr-evaluation", intent=UsageIntent.COMMERCIAL_PUBLISHING)
    assert select_kurmanji_provider("meta-mms-kmr-evaluation", intent=UsageIntent.TEST).license_review_required


def test_professional_provider_requires_all_paid_execution_gates(monkeypatch):
    monkeypatch.setenv("KURDISH_TTS_API_KEY", "secret")
    transport = Transport(TTSHttpResponse(200, "audio/wav", wav()))
    provider = KurdishTTSProvider(KurdishTTSConfig(), transport=transport)
    with pytest.raises(KurmanjiTTSUsageError, match="owner_approved"):
        provider.synthesize(text="Silav", voice_id="kurmanji_aden", approval=approval(owner_approved=False))
    with pytest.raises(KurmanjiTTSUsageError, match="external_provider_enabled"):
        provider.synthesize(
            text="Silav", voice_id="kurmanji_aden",
            approval=approval(external_provider_enabled=False),
        )
    assert transport.calls == []


def test_api_key_is_required_and_never_serialized(monkeypatch):
    monkeypatch.delenv("KURDISH_TTS_API_KEY", raising=False)
    provider = KurdishTTSProvider(KurdishTTSConfig(), transport=Transport(None))
    assert provider.configuration_summary()["api_key_present"] is False
    with pytest.raises(KurmanjiTTSConfigurationError):
        provider.synthesize(text="Silav", voice_id="kurmanji_aden", approval=approval())


def test_professional_provider_sends_kmr_and_accepts_valid_pcm_wav(monkeypatch):
    monkeypatch.setenv("KURDISH_TTS_API_KEY", "secret")
    transport = Transport(TTSHttpResponse(200, "audio/wav; charset=binary", wav()))
    provider = KurdishTTSProvider(KurdishTTSConfig(), transport=transport)
    response = provider.synthesize(text=" Silav dinyayê ", voice_id="kurmanji_aden", approval=approval())
    assert response.body.startswith(b"RIFF")
    _, call = transport.calls[0]
    assert call["payload"] == {
        "text": "Silav dinyayê",
        "speaker_id": "kurmanji_aden",
        "model_version": "v5",
    }
    assert call["api_key"] == "secret"


@pytest.mark.parametrize("body", [b"", b"not wave", wav()[:-1]])
def test_strict_wav_validation_rejects_malformed_audio(body):
    with pytest.raises(KurmanjiTTSResponseError):
        validate_pcm_wav(body)


def test_config_rejects_non_https_endpoint():
    with pytest.raises(ValueError, match="HTTPS"):
        KurdishTTSConfig("http://www.kurdishtts.com")


def test_config_rejects_untrusted_host_that_could_receive_api_key():
    with pytest.raises(ValueError, match="host"):
        KurdishTTSConfig("https://api.example.test")
