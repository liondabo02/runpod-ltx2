from __future__ import annotations

import json

import pytest

from ahos.adapters import runpod


def test_submit_is_blocked_by_default(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("AHOS_RUNPOD_ENABLED", raising=False)

    with pytest.raises(PermissionError):
        runpod.submit(
            tmp_path,
            job_id="j-1",
            kind="video",
            prompt="klip",
            project=str(tmp_path),
        )


def test_submit_requires_zero_budget(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AHOS_RUNPOD_ENABLED", "1")
    monkeypatch.setenv("AHOS_RUNPOD_ENDPOINT_VIDEO", "http://127.0.0.1:1/run")
    monkeypatch.setenv("AHOS_RUNPOD_MAX_USD", "0")

    with pytest.raises(PermissionError):
        runpod.submit(
            tmp_path,
            job_id="j-2",
            kind="video",
            prompt="klip",
            project=str(tmp_path),
            max_usd=1.5,
        )


def test_unknown_kind_is_rejected(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AHOS_RUNPOD_ENABLED", "1")

    with pytest.raises(ValueError):
        runpod.submit(
            tmp_path,
            job_id="j-3",
            kind="mining",
            prompt="x",
            project=str(tmp_path),
        )


def test_enabled_submit_writes_request(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AHOS_RUNPOD_ENABLED", "1")
    # Uç nokta testin kendi ortamından gelir; makinede tanımlı olmasına güvenme.
    monkeypatch.setenv("AHOS_RUNPOD_ENDPOINT_VIDEO", "http://127.0.0.1:1/run")
    monkeypatch.setenv("AHOS_RUNPOD_ENDPOINT", "http://127.0.0.1:1/run")

    path = runpod.submit(
        tmp_path,
        job_id="j-4",
        kind="video",
        prompt="klip",
        project=str(tmp_path),
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["max_usd"] == 0.0
    assert payload["kind"] == "video"


def test_status_reports_disabled_by_default(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("AHOS_RUNPOD_ENABLED", raising=False)

    state = runpod.status(tmp_path)

    assert state["enabled"] is False
    assert "kapalı" in state["state"]
