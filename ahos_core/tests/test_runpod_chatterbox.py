import base64

import pytest

from ahos.audio_pipeline import AudioJob, AudioTaskType
from ahos.runpod_chatterbox import (
    PaidExecutionApproval,
    RunPodChatterboxConfig,
    RunPodChatterboxProvider,
    RunPodChatterboxResponseError,
    RunPodExecutionGateError,
)


def wav_bytes():
    return b"RIFF" + (b"\x00" * 4) + b"WAVE" + (b"\x00" * 64)


def wav_b64():
    return base64.b64encode(wav_bytes()).decode("ascii")


class FakeTransport:
    def __init__(self, response=None):
        self.calls = []
        self.response = response or {
            "status": "COMPLETED",
            "output": {
                "ok": True,
                "audio_base64": wav_b64(),
                "format": "wav",
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


def test_payload_requires_character_reference_audio():
    with pytest.raises(ValueError):
        RunPodChatterboxProvider.speech_payload(
            text="Merhaba",
            language_id="tr",
            voice_id="aden-tr-v1",
            reference_audio_base64=None,
        )


def test_payload_accepts_target_studio_languages():
    payload = RunPodChatterboxProvider.speech_payload(
        text="Hallo",
        language_id="de",
        voice_id="aden-de-v1",
        reference_audio_base64=wav_b64(),
    )
    assert payload["input"]["language_id"] == "de"
    assert payload["input"]["voice_id"] == "aden-de-v1"


def test_paid_execution_requires_triple_gate(monkeypatch):
    monkeypatch.setenv("RUNPOD_API_KEY", "secret-test-value")
    transport = FakeTransport()
    provider = RunPodChatterboxProvider(
        RunPodChatterboxConfig(endpoint_id="cb123"),
        transport=transport,
    )

    with pytest.raises(RunPodExecutionGateError):
        provider.synthesize(
            text="Hello",
            language_id="en",
            voice_id="aden-en-v1",
            reference_audio_base64=wav_b64(),
            approval=PaidExecutionApproval(
                owner_approved=True,
                execution_enabled=False,
                paid_provider_enabled=True,
            ),
        )

    assert transport.calls == []


def test_runsync_response_returns_validated_wav(monkeypatch):
    monkeypatch.setenv("RUNPOD_API_KEY", "secret-test-value")
    transport = FakeTransport()
    provider = RunPodChatterboxProvider(
        RunPodChatterboxConfig(endpoint_id="cb123"),
        transport=transport,
    )

    audio = provider.synthesize(
        text="Bonjour",
        language_id="fr",
        voice_id="aden-fr-v1",
        reference_audio_base64=wav_b64(),
        approval=approval(),
    )

    assert audio.startswith(b"RIFF")
    assert transport.calls[0]["url"] == "https://api.runpod.ai/v2/cb123/runsync"
    assert transport.calls[0]["payload"]["input"]["language_id"] == "fr"


def test_synthesize_job_uses_audio_pipeline_voice_binding(monkeypatch):
    monkeypatch.setenv("RUNPOD_API_KEY", "secret-test-value")
    transport = FakeTransport()
    provider = RunPodChatterboxProvider(
        RunPodChatterboxConfig(endpoint_id="cb123"),
        transport=transport,
    )
    job = AudioJob(
        job_id="tts:S01E001:L1:tr",
        task_type=AudioTaskType.DIALOGUE_TTS,
        episode_id="S01E001",
        scene_id="SCENE-01",
        language="tr",
        speaker_character_id="aden",
        provider_id="chatterbox-multilingual",
        payload={
            "text": "Merhaba",
            "voice_id": "aden-tr-v1",
            "speaking_style": "warm",
            "reference_audio_uri": "private://voices/aden/tr/reference.wav",
        },
        paid=True,
        external=True,
    )

    audio = provider.synthesize_job(
        job,
        reference_audio_base64=wav_b64(),
        approval=approval(),
    )

    assert audio.startswith(b"RIFF")
    assert transport.calls[0]["payload"]["input"]["voice_id"] == "aden-tr-v1"


def test_bad_audio_response_is_rejected(monkeypatch):
    monkeypatch.setenv("RUNPOD_API_KEY", "secret-test-value")
    transport = FakeTransport(
        response={
            "status": "COMPLETED",
            "output": {
                "ok": True,
                "audio_base64": base64.b64encode(b"not wav").decode("ascii"),
            },
        }
    )
    provider = RunPodChatterboxProvider(
        RunPodChatterboxConfig(endpoint_id="cb123"),
        transport=transport,
    )

    with pytest.raises(RunPodChatterboxResponseError):
        provider.synthesize(
            text="Hello",
            language_id="en",
            voice_id="aden-en-v1",
            reference_audio_base64=wav_b64(),
            approval=approval(),
        )


def test_configuration_summary_hides_secret(monkeypatch):
    monkeypatch.setenv("RUNPOD_API_KEY", "do-not-serialize-me")
    provider = RunPodChatterboxProvider(
        RunPodChatterboxConfig(endpoint_id="cb123")
    )
    summary = provider.configuration_summary()

    assert summary["api_key_present"] is True
    assert "do-not-serialize-me" not in str(summary)
