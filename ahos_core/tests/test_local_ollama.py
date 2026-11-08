from __future__ import annotations

import json
import sys

import pytest

from ahos import local_ollama
from ahos.llm_executor import ModelError, ModelSettings


def _settings(**overrides) -> ModelSettings:
    values = dict(
        base_url=local_ollama.BASE,
        api_key="local-only",
        model=local_ollama.MODEL,
        max_usd_per_run=0,
        input_usd_per_1k=0,
        output_usd_per_1k=0,
        timeout_seconds=10,
    )
    values.update(overrides)
    return ModelSettings(**values)


def test_transport_refuses_foreign_endpoint() -> None:
    with pytest.raises(ModelError):
        local_ollama.transport("s", "p", _settings(base_url="https://api.example/v1"))


def test_transport_refuses_foreign_model() -> None:
    with pytest.raises(ModelError):
        local_ollama.transport("s", "p", _settings(model="gpt-4o-mini"))


def test_transport_refuses_oversized_context() -> None:
    with pytest.raises(ModelError):
        local_ollama.transport("s" * 7000, "p" * 6000, _settings())


def test_request_allows_only_known_endpoints() -> None:
    for endpoint in ("delete", "pull", "download", "../api/tags"):
        with pytest.raises(ModelError):
            local_ollama.request(endpoint)


def test_low_memory_blocks_before_any_request(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setenv("AHOS_MIN_FREE_MB", "2048")
    monkeypatch.setattr(local_ollama, "memory_available", lambda: 1024 ** 3)
    monkeypatch.setattr(local_ollama, "request", lambda *a, **k: calls.append("x"))
    with pytest.raises(ModelError, match="2 GiB"):
        local_ollama.transport("sys", "prompt", _settings())
    assert calls == [], "bellek yetersizken modele hiç gidilmemeli"


def test_unavailable_lock_reports_wait(monkeypatch) -> None:
    class Locked:
        def __enter__(self):
            return False

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(local_ollama, "inference_lock", lambda: Locked())
    with pytest.raises(ModelError, match="başka görevde"):
        local_ollama.transport("sys", "prompt", _settings())


def test_transport_sends_bounded_deterministic_request(monkeypatch) -> None:
    seen: dict[str, object] = {}

    class Free:
        def __enter__(self):
            return True

        def __exit__(self, *exc):
            return False

    def fake_request(endpoint, body=None, timeout=5):
        if endpoint == "tags":
            return {"models": [{"name": local_ollama.MODEL}]}
        seen["body"] = body
        return {"done": True, "done_reason": "stop", "response": '{"ok": true}'}

    monkeypatch.setattr(local_ollama, "inference_lock", lambda: Free())
    monkeypatch.setattr(local_ollama, "memory_available", lambda: 4 * 1024 ** 3)
    monkeypatch.setattr(local_ollama, "request", fake_request)

    answer = local_ollama.transport("sys", "prompt", _settings())

    assert answer == '{"ok": true}'
    body = seen["body"]
    assert body["keep_alive"] == 0
    assert body["stream"] is False
    assert body["format"] == "json"
    assert body["options"]["temperature"] == 0


def test_transport_rejects_truncated_model_output(monkeypatch) -> None:
    class Free:
        def __enter__(self):
            return True

        def __exit__(self, *exc):
            return False

    def fake_request(endpoint, body=None, timeout=5):
        if endpoint == "tags":
            return {"models": [{"name": local_ollama.MODEL}]}
        return {"done": True, "done_reason": "length", "response": "{\"partial\":"}

    monkeypatch.setattr(local_ollama, "inference_lock", lambda: Free())
    monkeypatch.setattr(local_ollama, "memory_available", lambda: 4 * 1024 ** 3)
    monkeypatch.setattr(local_ollama, "request", fake_request)

    with pytest.raises(ModelError, match="tamamlanmadı"):
        local_ollama.transport("sys", "prompt", _settings())


def test_installed_model_check_does_not_download(monkeypatch) -> None:
    class Free:
        def __enter__(self):
            return True

        def __exit__(self, *exc):
            return False

    called: list[str] = []

    def fake_request(endpoint, body=None, timeout=5):
        called.append(endpoint)
        return {"models": [{"name": "other-model"}]}

    monkeypatch.setattr(local_ollama, "inference_lock", lambda: Free())
    monkeypatch.setattr(local_ollama, "memory_available", lambda: 4 * 1024 ** 3)
    monkeypatch.setattr(local_ollama, "request", fake_request)

    with pytest.raises(ModelError, match="kurulu değil"):
        local_ollama.transport("sys", "prompt", _settings())

    assert called == ["tags"], "model yoksa indirme/pull çağrısı yapılmamalı"
