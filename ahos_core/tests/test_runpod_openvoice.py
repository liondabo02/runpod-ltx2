import base64

import pytest

from ahos.runpod_ltx2 import PaidExecutionApproval
from ahos.runpod_openvoice import (
    RunPodOpenVoiceConfig, RunPodOpenVoiceProvider, RunPodOpenVoiceResponseError,
)


WAV = b"RIFF" + b"\0" * 4 + b"WAVE" + b"\0" * 64


class Transport:
    def __init__(self, output=None):
        self.calls = []
        self.output = output or {"status": "COMPLETED", "output": {
            "ok": True, "identity_transfer": True,
            "source_linguistics_preserved": True,
            "audio_base64": base64.b64encode(WAV).decode(),
        }}

    def request_json(self, method, url, *, api_key, payload=None, timeout=30):
        self.calls.append((method, url, api_key, payload, timeout))
        return self.output


def approval():
    return PaidExecutionApproval(True, True, True)


def test_conversion_sends_source_and_target_without_text_regeneration(monkeypatch):
    monkeypatch.setenv("RUNPOD_API_KEY", "secret")
    transport = Transport()
    provider = RunPodOpenVoiceProvider(RunPodOpenVoiceConfig("openvoice1"), transport=transport)
    assert provider.convert(source_audio=WAV, target_reference_audio=WAV,
                            character_id="aden", approval=approval()) == WAV
    payload = transport.calls[0][3]["input"]
    assert payload["operation"] == "tone_color_convert"
    assert payload["language"] == "ku-latn"
    assert payload["preserve_source_linguistics"] is True
    assert "text" not in payload


def test_conversion_rejects_worker_without_identity_evidence(monkeypatch):
    monkeypatch.setenv("RUNPOD_API_KEY", "secret")
    transport = Transport({"status": "COMPLETED", "output": {
        "ok": True, "audio_base64": base64.b64encode(WAV).decode()
    }})
    provider = RunPodOpenVoiceProvider(RunPodOpenVoiceConfig("openvoice1"), transport=transport)
    with pytest.raises(RunPodOpenVoiceResponseError, match="identity-transfer"):
        provider.convert(source_audio=WAV, target_reference_audio=WAV,
                         character_id="aden", approval=approval())


def test_payload_rejects_non_wav_and_non_kurmanji():
    with pytest.raises(ValueError, match="RIFF"):
        RunPodOpenVoiceProvider.conversion_payload(
            source_audio=b"bad", target_reference_audio=WAV, character_id="aden"
        )
    with pytest.raises(ValueError, match="restricted"):
        RunPodOpenVoiceProvider.conversion_payload(
            source_audio=WAV, target_reference_audio=WAV,
            character_id="aden", language="tr"
        )
