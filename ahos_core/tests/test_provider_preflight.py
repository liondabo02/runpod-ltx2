"""Model inference health is distinct from /models HTTP health."""

from __future__ import annotations

import io
import json
import urllib.error

from ahos import provider_preflight


class Response:
    status = 200

    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size):
        return self.payload[:size]


def test_real_text_response_is_healthy(monkeypatch):
    seen = []

    def open_request(request, timeout):
        seen.append((request.full_url, json.loads(request.data), timeout))
        return Response(b'{"choices":[{"message":{"content":"READY"}}]}')

    monkeypatch.setattr(provider_preflight.urllib.request, "urlopen", open_request)
    result = provider_preflight.check_local_inference(
        "http://127.0.0.1:11434/v1", "qwen2.5-coder:1.5b", timeout=4
    )
    assert result.available and result.reason == "inference_ok"
    url, data, timeout = seen[0]
    assert url == "http://127.0.0.1:11434/v1/chat/completions"
    assert data["max_tokens"] == 12 and data["stream"] is False
    assert timeout == 4


def test_model_listing_is_not_enough(monkeypatch):
    monkeypatch.setattr(
        provider_preflight.urllib.request, "urlopen",
        lambda request, timeout: Response(b'{"data":[{"id":"model"}]}'),
    )
    result = provider_preflight.check_local_inference("http://127.0.0.1:11434", "model")
    assert not result.available and result.reason == "missing_choices"


def test_empty_answer_is_failure(monkeypatch):
    monkeypatch.setattr(
        provider_preflight.urllib.request, "urlopen",
        lambda request, timeout: Response(b'{"choices":[{"message":{"content":" "}}]}'),
    )
    result = provider_preflight.check_local_inference("http://127.0.0.1:11434/v1", "model")
    assert not result.available and result.reason == "no_generated_text"


def test_429_is_not_success(monkeypatch):
    def failed(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 429, "limited", {}, io.BytesIO())

    monkeypatch.setattr(provider_preflight.urllib.request, "urlopen", failed)
    result = provider_preflight.check_local_inference("http://127.0.0.1:11434/v1", "model")
    assert not result.available and result.reason == "rate_limited"


def test_remote_endpoint_is_denied_without_network(monkeypatch):
    def forbid(*args, **kwargs):
        raise AssertionError("must not call external endpoint")

    monkeypatch.setattr(provider_preflight.urllib.request, "urlopen", forbid)
    for url in ("https://openrouter.ai/api/v1", "http://169.254.169.254/v1",
                "http://example.com/v1", "http://localhost:11434/v1",
                "http://127.0.0.1:11434/v1?token=something"):
        result = provider_preflight.check_local_inference(url, "model")
        assert not result.available and result.reason == "remote_or_unsafe_endpoint"


def test_network_failure_is_explicit(monkeypatch):
    def failed(request, timeout):
        raise urllib.error.URLError("timeout")

    monkeypatch.setattr(provider_preflight.urllib.request, "urlopen", failed)
    result = provider_preflight.check_local_inference("http://127.0.0.1:11434/v1", "model")
    assert not result.available and result.reason == "unreachable_or_timeout"


def test_invalid_response_is_not_success(monkeypatch):
    monkeypatch.setattr(
        provider_preflight.urllib.request, "urlopen",
        lambda request, timeout: Response(b"not-json"),
    )
    result = provider_preflight.check_local_inference("http://127.0.0.1:11434/v1", "model")
    assert not result.available and result.reason == "malformed_inference_response"


def test_invalid_timeout_blocks_without_network():
    result = provider_preflight.check_local_inference("http://127.0.0.1:11434", "model", timeout=0)
    assert not result.available and result.reason == "invalid_model_or_timeout"


def test_select_free_model_uses_verified_fallback(monkeypatch):
    calls = []

    def verify(url, model, *, timeout):
        calls.append((url, model, timeout))
        return provider_preflight.Preflight(
            available=model == "good", model=model,
            reason="inference_ok" if model == "good" else "unreachable_or_timeout",
        )

    monkeypatch.setattr(provider_preflight, "check_local_inference", verify)
    selected, attempts = provider_preflight.select_free_model((
        ("http://127.0.0.1:11500/v1", "slow"),
        ("http://127.0.0.1:11434/v1", "good"),
        ("http://127.0.0.1:11434/v1", "unused"),
    ), timeout=4)
    assert selected is not None and selected.model == "good"
    assert [x.reason for x in attempts] == ["unreachable_or_timeout", "inference_ok"]
    assert len(calls) == 2


def test_select_free_model_fails_closed_when_no_real_inference(monkeypatch):
    monkeypatch.setattr(provider_preflight, "check_local_inference", lambda base, model, timeout: (
        provider_preflight.Preflight(False, model, "no_generated_text")
    ))
    selected, attempts = provider_preflight.select_free_model((
        ("http://127.0.0.1:11500/v1", "a"),
        ("http://127.0.0.1:11434/v1", "b"),
    ))
    assert selected is None and len(attempts) == 2


def test_runtime_provider_routing_requires_verified_generation(monkeypatch):
    from ahos import providers

    chain = [
        providers.Provider("tunnel", "http://127.0.0.1:11500/v1", "slow"),
        providers.Provider("local", "http://127.0.0.1:11434/v1", "good"),
    ]
    monkeypatch.setattr(providers, "default_chain", lambda: chain)
    verified = []

    def infer(base_url, model, *, timeout):
        verified.append((base_url, model))
        return provider_preflight.Preflight(
            model == "good", model,
            "inference_ok" if model == "good" else "unreachable_or_timeout",
        )

    monkeypatch.setattr(provider_preflight, "check_local_inference", infer)
    env = {"AHOS_PROVIDER_INFERENCE_CHECK": "1"}
    result = providers.apply_chain_to_env(environ=env)
    assert result["chosen"] == "local"
    assert env["AHOS_LLM_MODEL"] == "good"
    assert env["AHOS_LLM_BASE_URL"] == "http://127.0.0.1:11434/v1"
    assert env["AHOS_PROVIDER_REPORT"] == "tunnel=yok,local=ok"
    assert len(verified) == 2


def test_runtime_real_check_is_opt_in(monkeypatch):
    from ahos import providers

    monkeypatch.setattr(
        providers, "default_chain",
        lambda: [providers.Provider("tunnel", "http://127.0.0.1:11500/v1", "m")],
    )
    monkeypatch.setattr(provider_preflight, "check_local_inference",
                        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("must not run")))
    env = {}
    result = providers.apply_chain_to_env(environ=env, probe_fn=lambda provider: True)
    assert result["chosen"] == "tunnel"


def test_runtime_real_check_clears_stale_provider_when_all_down(monkeypatch):
    from ahos import providers

    monkeypatch.setattr(
        providers, "default_chain",
        lambda: [providers.Provider("tunnel", "http://127.0.0.1:11500/v1", "gone")],
    )
    monkeypatch.setattr(
        provider_preflight, "check_local_inference",
        lambda base, model, timeout: provider_preflight.Preflight(
            False, model, "unreachable_or_timeout"
        ),
    )
    env = {
        "AHOS_PROVIDER_INFERENCE_CHECK": "1",
        "AHOS_LLM_BASE_URL": "http://127.0.0.1:11500/v1",
        "AHOS_LLM_MODEL": "gone",
        "AHOS_LLM_API_KEY": "local-only",
        "AHOS_ACTIVE_PROVIDER": "tunnel",
    }
    report = providers.apply_chain_to_env(environ=env)
    assert report["chosen"] is None
    assert env["AHOS_PROVIDER_INFERENCE_OK"] == "0"
    assert "AHOS_LLM_MODEL" not in env
    assert "AHOS_ACTIVE_PROVIDER" not in env
