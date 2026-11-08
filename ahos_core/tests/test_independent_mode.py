"""Owner-controlled cloud-first mode cannot spend API credits."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "ops/oracle/independent_mode.py"
spec = importlib.util.spec_from_file_location("independent_mode", SCRIPT)
assert spec is not None and spec.loader is not None
mode = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mode)


def test_transform_keeps_approval_and_removes_paid_endpoints():
    original = (
        "# AHOS\nAHOS_EXECUTOR=model\nAHOS_LLM_BASE_URL=https://provider/v1\n"
        "AHOS_LLM_API_KEY=secret\nAHOS_LLM_MODEL=paid/model\n"
        "AHOS_ALLOW_PAID_LLM=1\nAHOS_LLM_MAX_USD=0.02\n"
        "AHOS_FALLBACK_BASE_URL=http://127.0.0.1:11500/v1\n"
        "AHOS_AUTO_APPROVE_RISK=low\n"
    )
    result = mode.transform(original)
    assert "provider" not in result and "secret" not in result
    assert "AHOS_ALLOW_PAID_LLM=0" in result
    assert "AHOS_LLM_MAX_USD=0" in result
    assert "AHOS_LLM_BASE_URL=http://127.0.0.1:11500/v1" in result
    assert "AHOS_LLM_MODEL=qwen2.5-coder:3b" in result
    assert "AHOS_AUTO_APPROVE_RISK=low" in result
    assert "AHOS_FALLBACK_BASE_URL=" not in result
    assert mode.transform(result) == result


def test_no_connection_means_no_changes(tmp_path):
    path = tmp_path / "model.env"
    original = b"AHOS_LLM_MODEL=original\n"
    path.write_bytes(original)
    with pytest.raises(RuntimeError, match="not confirmed"):
        mode.switch(path, probe=lambda: False)
    assert path.read_bytes() == original
    assert list(tmp_path.glob("*.bak")) == []


def test_zero_spend_and_original_backup(tmp_path, monkeypatch):
    monkeypatch.setattr(mode.Path, "home", lambda: tmp_path)
    path = tmp_path / "runtime" / "model.env"
    path.parent.mkdir()
    path.write_text("AHOS_LLM_API_KEY=private\nAHOS_LLM_MAX_USD=1\n", encoding="utf-8")
    result = mode.switch(path, probe=lambda: True)
    assert result["result"] == "switched_next_launch"
    assert "private" not in path.read_text()
    assert Path(result["backup"]).read_text() == "AHOS_LLM_API_KEY=private\nAHOS_LLM_MAX_USD=1\n"
    assert str(result["backup"]).find("runtime") < 0
    assert mode.switch(path, probe=lambda: True)["result"] == "already_independent"
    assert mode.describe(path, probe=lambda: True)["paid_disabled"] is True


def test_malformed_probe_fails_closed(monkeypatch):
    def fail(url, timeout):
        raise TimeoutError()
    assert mode.cloud_ready(request=fail) is False


def test_restore_and_refuse_unapproved_backup(tmp_path, monkeypatch):
    monkeypatch.setattr(mode.Path, "home", lambda: tmp_path)
    path = tmp_path / "runtime" / "model.env"
    path.parent.mkdir()
    original = b"AHOS_LLM_MODEL=original\nAHOS_ALLOW_PAID_LLM=1\n"
    path.write_bytes(original)
    backup = Path(mode.switch(path, probe=lambda: True)["backup"])
    assert mode.restore(path, backup)["result"] == "original_config_restored"
    assert path.read_bytes() == original
    with pytest.raises(ValueError):
        mode.restore(path, tmp_path / "arbitrary.bak")
