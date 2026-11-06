import os

import pytest

from ahos.runpod_ltx2 import (
    PaidExecutionApproval,
    RunPodExecutionGateError,
    RunPodLTX2Config,
    RunPodLTX2Provider,
)
from ahos.visual_pipeline import RenderJob


class FakeTransport:
    def __init__(self):
        self.calls = []

    def request_json(
        self,
        method,
        url,
        *,
        api_key,
        payload=None,
        timeout=30.0,
    ):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "api_key": api_key,
                "payload": payload,
            }
        )
        return {"id": "job-123", "status": "IN_QUEUE"}


def job():
    return RenderJob(
        job_id="render:S01E001:SHOT-01",
        episode_id="S01E001",
        shot_id="SHOT-01",
        prompt_id="prompt-01",
        output_asset_id="output-01",
        mode="video",
        seed=123,
        positive_prompt="Aden and Kaan in a warm family scene",
        negative_prompt="identity drift",
        reference_asset_ids=("charref:aden:v1", "charref:kaan:v1"),
        continuity_constraints=("keep identity",),
        style_id="family-2d-v1",
        duration_seconds=6,
        output_prefix="S01E001/SHOT-01/123",
    )


def test_endpoint_url_uses_official_v2_shape():
    config = RunPodLTX2Config(endpoint_id="abc123")
    assert config.endpoint_base == "https://api.runpod.ai/v2/abc123"


def test_health_payload_matches_existing_worker_contract():
    assert RunPodLTX2Provider.health_payload() == {"input": {"ping": True}}


def test_render_payload_matches_ltx2_worker_contract():
    payload = RunPodLTX2Provider.render_payload(job())
    request = payload["input"]

    assert request["workflow_api"] == "image_to_video.api.json"
    assert request["positive_prompt"]
    assert request["duration_seconds"] == 6
    assert request["fps"] == 24
    assert request["steps"] == 8
    assert request["seed"] == 123
    assert request["width"] == 1024
    assert request["height"] == 576
    assert request["wait"] is True


def test_invalid_ltx_resolution_is_rejected():
    with pytest.raises(ValueError):
        RunPodLTX2Provider.render_payload(job(), width=1023, height=576)


def test_paid_ping_is_blocked_without_all_three_gates(monkeypatch):
    monkeypatch.setenv("RUNPOD_API_KEY", "secret-test-value")
    transport = FakeTransport()
    provider = RunPodLTX2Provider(
        RunPodLTX2Config(endpoint_id="abc123"),
        transport=transport,
    )

    with pytest.raises(RunPodExecutionGateError):
        provider.ping(
            approval=PaidExecutionApproval(
                owner_approved=True,
                execution_enabled=False,
                paid_provider_enabled=True,
            )
        )

    assert transport.calls == []


def test_submit_calls_run_only_after_explicit_owner_paid_execution(monkeypatch):
    monkeypatch.setenv("RUNPOD_API_KEY", "secret-test-value")
    transport = FakeTransport()
    provider = RunPodLTX2Provider(
        RunPodLTX2Config(endpoint_id="abc123"),
        transport=transport,
    )

    result = provider.submit(
        RunPodLTX2Provider.render_payload(job()),
        approval=PaidExecutionApproval(
            owner_approved=True,
            execution_enabled=True,
            paid_provider_enabled=True,
        ),
        synchronous=False,
    )

    assert result["id"] == "job-123"
    assert len(transport.calls) == 1
    assert transport.calls[0]["method"] == "POST"
    assert transport.calls[0]["url"].endswith("/abc123/run")


def test_configuration_summary_never_contains_api_key(monkeypatch):
    monkeypatch.setenv("RUNPOD_API_KEY", "do-not-serialize-me")
    provider = RunPodLTX2Provider(RunPodLTX2Config(endpoint_id="abc123"))
    summary = provider.configuration_summary()

    assert summary["api_key_present"] is True
    assert "do-not-serialize-me" not in str(summary)
