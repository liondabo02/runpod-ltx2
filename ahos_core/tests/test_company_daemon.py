import json
import subprocess

import pytest

from ahos.company_daemon import build_service


def test_daemon_defaults_to_safe_monitor_mode(tmp_path):
    service = build_service(tmp_path, tmp_path / "missing.json", 0.01)
    assert service.run_once() == "idle"
    heartbeat = json.loads((tmp_path / "company-service-heartbeat.json").read_text())
    assert heartbeat["automation_results"] == ["coding:disabled"]


def test_enabled_coding_requires_explicit_builder_and_allowlist(tmp_path):
    config = tmp_path / "company-service-config.json"
    config.write_text(json.dumps({"coding_supervisor": {"enabled": True}}))
    with pytest.raises(ValueError, match="builder_command"):
        build_service(tmp_path, config, 1.0)


def test_company_config_accepts_windows_utf8_bom(tmp_path):
    config = tmp_path / "company-service-config.json"
    config.write_text('{"coding_supervisor":{"enabled":false}}', encoding="utf-8-sig")
    service = build_service(tmp_path, config, 0.01)
    assert service.run_once() == "idle"
    heartbeat = json.loads((tmp_path / "company-service-heartbeat.json").read_text())
    assert heartbeat["automation_results"] == ["coding:disabled"]


def test_daemon_preserves_nested_builder_options_as_json(tmp_path, monkeypatch):
    config = tmp_path / "company-service-config.json"
    config.write_text(json.dumps({"coding_supervisor": {
        "enabled": True,
        "builder_command": ["python", "-m", "builder", "--model", "openrouter/free"],
        "allowed_test_executables": ["python"],
    }}))
    captured = {}

    def fake_run(command, **_kwargs):
        captured["command"] = command
        return subprocess.CompletedProcess(command, 0, stdout="null", stderr="")

    monkeypatch.setattr("ahos.company_daemon.subprocess.run", fake_run)
    assert build_service(tmp_path, config, 0.01).run_once() == "idle"
    command = captured["command"]
    encoded = command[command.index("--builder-command-json") + 1]
    assert json.loads(encoded) == ["python", "-m", "builder", "--model", "openrouter/free"]
