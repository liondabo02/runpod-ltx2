import base64

import pytest

from ahos.runpod_ltx2 import PaidExecutionApproval
from ahos.runpod_qwen3_voice_design import (
    RunPodExecutionGateError,
    RunPodQwen3VoiceDesignConfig,
    RunPodQwen3VoiceDesignProvider,
    RunPodQwen3VoiceDesignResponseError,
)


def wav_bytes():
    return b"RIFF" + (b"\x00" * 4) + b"WAVE" + (b"\x00" * 64)


class FakeTransport:
    def __init__(self, response=None):
        self.calls = []
        self.response = response or {
            "status": "COMPLETED",
            "output": {
                "ok": True,
                "audio_base64": base64.b64encode(wav_bytes()).decode("ascii"),
                "synthetic_voice": True,
                "canonical_binding_created": False,
            },
        }

    def request_json(self, method, url, *, api_key, payload=None, timeout=30.0):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "api_key": api_key,
                "payload": payload,
                "timeout": timeout,
            }
        )
        return self.response


def approval():
    return PaidExecutionApproval(
        owner_approved=True,
        execution_enabled=True,
        paid_provider_enabled=True,
    )


def test_design_payload_encodes_age_appropriate_instruction():
    payload = RunPodQwen3VoiceDesignProvider.design_payload(
        text="Hello, shall we play together today?",
        language="English",
        instruct=(
            "Fictional preschool-age girl about three years old. "
            "Natural small child voice. Never sound like an adult."
        ),
        candidate_id="aden-qwen3-trial-01",
        seed=17,
    )
    assert payload["input"]["language"] == "English"
    assert "three years old" in payload["input"]["instruct"]
    assert payload["input"]["candidate_id"] == "aden-qwen3-trial-01"


def test_turkish_is_not_claimed_as_voicedesign_language():
    with pytest.raises(ValueError):
        RunPodQwen3VoiceDesignProvider.design_payload(
            text="Merhaba",
            language="Turkish",
            instruct="young child voice",
            candidate_id="bad",
        )


def test_paid_execution_gate_blocks_network(monkeypatch):
    monkeypatch.setenv("RUNPOD_API_KEY", "secret-test-value")
    transport = FakeTransport()
    provider = RunPodQwen3VoiceDesignProvider(
        RunPodQwen3VoiceDesignConfig(endpoint_id="qwen123"),
        transport=transport,
    )
    with pytest.raises(RunPodExecutionGateError):
        provider.design(
            text="Hello",
            language="English",
            instruct="Fictional preschool child",
            candidate_id="aden-candidate",
            approval=PaidExecutionApproval(
                owner_approved=True,
                execution_enabled=False,
                paid_provider_enabled=True,
            ),
        )
    assert transport.calls == []


def test_successful_runsync_returns_validated_wav(monkeypatch):
    monkeypatch.setenv("RUNPOD_API_KEY", "secret-test-value")
    transport = FakeTransport()
    provider = RunPodQwen3VoiceDesignProvider(
        RunPodQwen3VoiceDesignConfig(endpoint_id="qwen123"),
        transport=transport,
    )
    audio = provider.design(
        text="Hello",
        language="English",
        instruct="Fictional preschool child",
        candidate_id="aden-candidate",
        approval=approval(),
    )
    assert audio.startswith(b"RIFF")
    assert transport.calls[0]["url"] == "https://api.runpod.ai/v2/qwen123/runsync"


def test_bad_audio_is_rejected(monkeypatch):
    monkeypatch.setenv("RUNPOD_API_KEY", "secret-test-value")
    transport = FakeTransport(
        {
            "status": "COMPLETED",
            "output": {
                "ok": True,
                "audio_base64": base64.b64encode(b"not wav").decode("ascii"),
                "synthetic_voice": True,
                "canonical_binding_created": False,
            },
        }
    )
    provider = RunPodQwen3VoiceDesignProvider(
        RunPodQwen3VoiceDesignConfig(endpoint_id="qwen123"),
        transport=transport,
    )
    with pytest.raises(RunPodQwen3VoiceDesignResponseError):
        provider.design(
            text="Hello",
            language="English",
            instruct="Fictional preschool child",
            candidate_id="aden-candidate",
            approval=approval(),
        )


def test_configuration_summary_hides_secret(monkeypatch):
    monkeypatch.setenv("RUNPOD_API_KEY", "do-not-serialize-me")
    provider = RunPodQwen3VoiceDesignProvider(
        RunPodQwen3VoiceDesignConfig(endpoint_id="qwen123")
    )
    summary = provider.configuration_summary()
    assert summary["api_key_present"] is True
    assert "do-not-serialize-me" not in str(summary)
