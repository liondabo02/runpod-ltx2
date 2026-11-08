"""tools/runpod_preflight.py â€” anahtarÄ± sÄ±zdÄ±rmadan hazÄ±rlÄ±k kontrolÃ¼."""
from __future__ import annotations

import json
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS))


def test_env_file_only_loads_allowed_keys(tmp_path, monkeypatch):
    import runpod_preflight

    env = tmp_path / ".env.runtime"
    env.write_text(
        "RUNPOD_LTX_ENDPOINT_ID=abc123\n"
        "RUNPOD_API_KEY=secret-value\n"
        "OPENAI_API_KEY=should-not-load\n",
        encoding="utf-8",
    )
    for name in ("RUNPOD_LTX_ENDPOINT_ID", "RUNPOD_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)

    loaded = runpod_preflight.load_env(env)

    assert loaded == {"RUNPOD_LTX_ENDPOINT_ID": "abc123", "RUNPOD_API_KEY": "secret-value"}
    assert "OPENAI_API_KEY" not in loaded


def test_preflight_reports_ready_and_never_prints_secret(tmp_path, monkeypatch):
    import runpod_preflight

    monkeypatch.setattr(runpod_preflight, "ENV_FILES", (tmp_path / "yok.env",))
    monkeypatch.setenv("RUNPOD_LTX_ENDPOINT_ID", "abc123")
    monkeypatch.setenv("RUNPOD_API_KEY", "secret-value")

    result = runpod_preflight.preflight()

    assert result["ready"] is True
    assert result["api_key_present"] is True
    assert "secret-value" not in json.dumps(result)
    assert result["spending"].startswith("blocked")


def test_preflight_lists_missing_without_credentials(tmp_path, monkeypatch):
    import runpod_preflight

    monkeypatch.setattr(runpod_preflight, "ENV_FILES", (tmp_path / "yok.env",))
    monkeypatch.delenv("RUNPOD_LTX_ENDPOINT_ID", raising=False)
    monkeypatch.delenv("RUNPOD_API_KEY", raising=False)

    result = runpod_preflight.preflight()

    assert result["ready"] is False
    assert "RUNPOD_LTX_ENDPOINT_ID" in result["missing"]
    assert "RUNPOD_API_KEY" in result["missing"]


def test_payload_preview_uses_ltx_contract_and_never_contains_credentials(tmp_path, monkeypatch):
    import runpod_preflight

    monkeypatch.setattr(runpod_preflight, "ENV_FILES", (tmp_path / "yok.env",))
    payload = runpod_preflight.payload_preview()

    assert payload["workflow_api"] == "image_to_video.api.json"
    assert payload["duration_seconds"] == 6
    assert payload["width"] % 32 == 0 and payload["height"] % 32 == 0
    assert "input_image_base64" in payload
    assert "RUNPOD_API_KEY" not in json.dumps(payload)

