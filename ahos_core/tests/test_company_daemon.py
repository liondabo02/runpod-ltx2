import json

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
