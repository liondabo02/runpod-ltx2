import pytest

from ahos.audio_pipeline import AudioJob, AudioTaskType
from ahos.runpod_kokoro import (
    BinaryHttpResponse,
    PaidExecutionApproval,
    RunPodExecutionGateError,
    RunPodKokoroConfig,
    RunPodKokoroProvider,
    RunPodKokoroResponseError,
)


class FakeBinaryTransport:
    def __init__(self, *, body=None, status_code=200, content_type="audio/wav"):
        self.calls = []
        self.body = body if body is not None else (
            b"RIFF" + b"\x00\x00\x00\x00" + b"WAVE" + b"data"
        )
        self.status_code = status_code
        self.content_type = content_type

    def request_bytes(
        self,
        method,
        url,
        *,
        api_key,
        payload=None,
        timeout=330.0,
    ):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "api_key": api_key,
                "payload": payload,
                "timeout": timeout,
            }
        )
        return BinaryHttpResponse(
            status_code=self.status_code,
            content_type=self.content_type,
            body=self.body,
        )


def approval():
    return PaidExecutionApproval(
        owner_approved=True,
        execution_enabled=True,
        paid_provider_enabled=True,
    )


def audio_job():
    return AudioJob(
        job_id="tts:S01E001:L1:en",
        task_type=AudioTaskType.DIALOGUE_TTS,
        episode_id="S01E001",
        scene_id="SCENE-01",
        language="en",
        speaker_character_id="aden",
        provider_id="runpod-kokoro",
        payload={
            "text": "Hello.",
            "voice_id": "aden-v1",
            "speaking_style": "warm",
            "reference_audio_uri": None,
        },
        paid=True,
        external=True,
    )


def test_load_balancer_url_uses_endpoint_subdomain():
    config = RunPodKokoroConfig(endpoint_id="abc123")
    assert config.endpoint_base == "https://abc123.api.runpod.ai"


def test_speech_payload_matches_proven_kokoro_contract():
    payload = RunPodKokoroProvider.speech_payload(
        text="Hello",
        voice_id="af_heart",
        response_format="wav",
        speed=1.0,
    )
    assert payload == {
        "model": "tts-1",
        "input": "Hello",
        "voice": "af_heart",
        "response_format": "wav",
        "speed": 1.0,
    }


def test_invalid_abstract_character_voice_is_not_silently_substituted():
    with pytest.raises(ValueError):
        RunPodKokoroProvider.speech_payload(
            text="Hello",
            voice_id="aden-v1",
        )


def test_paid_tts_is_blocked_without_all_three_gates(monkeypatch):
    monkeypatch.setenv("RUNPOD_API_KEY", "secret-test-value")
    transport = FakeBinaryTransport()
    provider = RunPodKokoroProvider(
        RunPodKokoroConfig(endpoint_id="abc123"),
        transport=transport,
    )

    with pytest.raises(RunPodExecutionGateError):
        provider.synthesize(
            text="Hello",
            voice_id="af_heart",
            approval=PaidExecutionApproval(
                owner_approved=True,
                execution_enabled=False,
                paid_provider_enabled=True,
            ),
        )

    assert transport.calls == []


def test_real_contract_posts_binary_audio_after_explicit_approval(monkeypatch):
    monkeypatch.setenv("RUNPOD_API_KEY", "secret-test-value")
    transport = FakeBinaryTransport()
    provider = RunPodKokoroProvider(
        RunPodKokoroConfig(endpoint_id="abc123"),
        transport=transport,
    )

    response = provider.synthesize(
        text="Hello",
        voice_id="af_heart",
        approval=approval(),
    )

    assert response.status_code == 200
    assert response.body.startswith(b"RIFF")
    assert len(transport.calls) == 1
    assert transport.calls[0]["method"] == "POST"
    assert transport.calls[0]["url"] == (
        "https://abc123.api.runpod.ai/v1/audio/speech"
    )
    assert transport.calls[0]["payload"]["voice"] == "af_heart"


def test_synthesize_job_uses_audio_pipeline_assignment(monkeypatch):
    monkeypatch.setenv("RUNPOD_API_KEY", "secret-test-value")
    transport = FakeBinaryTransport()
    provider = RunPodKokoroProvider(
        RunPodKokoroConfig(endpoint_id="abc123"),
        transport=transport,
    )

    provider.synthesize_job(
        audio_job(),
        voice_id="af_heart",
        approval=approval(),
    )

    assert transport.calls[0]["payload"]["input"] == "Hello."


def test_bad_wav_body_is_rejected(monkeypatch):
    monkeypatch.setenv("RUNPOD_API_KEY", "secret-test-value")
    transport = FakeBinaryTransport(body=b'{"error":"not audio"}')
    provider = RunPodKokoroProvider(
        RunPodKokoroConfig(endpoint_id="abc123"),
        transport=transport,
    )

    with pytest.raises(RunPodKokoroResponseError):
        provider.synthesize(
            text="Hello",
            voice_id="af_heart",
            approval=approval(),
        )


def test_configuration_summary_never_contains_api_key(monkeypatch):
    monkeypatch.setenv("RUNPOD_API_KEY", "do-not-serialize-me")
    provider = RunPodKokoroProvider(RunPodKokoroConfig(endpoint_id="abc123"))
    summary = provider.configuration_summary()

    assert summary["api_key_present"] is True
    assert "do-not-serialize-me" not in str(summary)
