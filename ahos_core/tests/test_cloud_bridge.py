from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "ops" / "oracle" / "ahos_cloud_bridge.py"
SPEC = importlib.util.spec_from_file_location("ahos_cloud_bridge", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
bridge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge)


def test_remote_public_host_rejected():
    with pytest.raises(ValueError, match="127"):
        bridge.ollama_tags("203.0.113.50", 11434)


def test_unavailable_tunnel_is_not_mistaken_for_running_model(monkeypatch):
    def unavailable(*args, **kwargs):
        raise OSError("connection refused")

    monkeypatch.setattr(bridge, "urlopen", unavailable)
    assert bridge.ollama_tags() == ()


def test_only_loaded_model_may_be_staged(tmp_path):
    original = tmp_path / "ahos_core/runtime/model.env"
    original.parent.mkdir(parents=True)
    original.write_text("AHOS_LLM_MODEL=existing-paid-config\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="not verified"):
        bridge.stage(tmp_path, "deepseek-r1:7b", probe=lambda: ())
    assert original.read_text(encoding="utf-8") == "AHOS_LLM_MODEL=existing-paid-config\n"
    assert not (original.parent / "model.cloud.env").exists()


def test_staging_is_non_destructive_and_avoids_duplicate_writes(tmp_path):
    old = tmp_path / "ahos_core/runtime/model.env"
    old.parent.mkdir(parents=True)
    old.write_text("AHOS_LLM_MODEL=existing\n", encoding="utf-8")
    out = bridge.stage(tmp_path, "qwen2.5-coder:7b", probe=lambda: ("qwen2.5-coder:7b",))
    saved = out.read_text(encoding="utf-8")
    assert "AHOS_LLM_MODEL=qwen2.5-coder:7b" in saved
    assert "AHOS_LLM_BASE_URL=http://127.0.0.1:11500/v1" in saved
    assert "AHOS_LLM_MAX_USD=0" in saved
    assert old.read_text(encoding="utf-8") == "AHOS_LLM_MODEL=existing\n"
    with pytest.raises(FileExistsError):
        bridge.stage(tmp_path, "qwen2.5-coder:7b", probe=lambda: ("qwen2.5-coder:7b",))


def test_status_separates_cloud_data_from_live_connectivity(tmp_path):
    meta = tmp_path / "ops/oracle/last-instance.json"
    meta.parent.mkdir(parents=True)
    meta.write_text('{"instance_id":"fake","region":"eu-frankfurt-1","shape":"VM.Standard.A1.Flex","ssh_key":"PRIVATE"}')
    s = bridge.status(tmp_path, probe=lambda: ())
    assert s["vm_recorded"] is True
    assert s["tunnel_ready"] is False
    assert s["qwen_ready"] is False
    assert "PRIVATE" not in str(s)
