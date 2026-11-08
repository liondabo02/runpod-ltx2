"""Sağlık bekçisi: gerçek portlar ve zorunlu/isteğe bağlı ayrımı."""
from __future__ import annotations

import json

from ahos import health_guard as hg


def _runtime(tmp_path):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (runtime / "daemon-state.json").write_text(
        json.dumps({"status": "running", "ticks": 3}), encoding="utf-8")
    return runtime


def test_office_uses_real_port_8801():
    assert hg.SERVICES["office"].endswith(":8801/")
    assert "panel" in hg.REQUIRED_SERVICES
    assert "office" in hg.REQUIRED_SERVICES
    assert "tunnel" not in hg.REQUIRED_SERVICES


def test_optional_tunnel_down_is_warning_not_failure(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path)
    monkeypatch.setattr(hg, "_probe", lambda url: (False, "Timeout") if "11500" in url else (True, "HTTP 200"))
    monkeypatch.setattr(hg, "_counts", lambda runtime: {"blocked": 0})

    report = hg.check(runtime, fix=False)

    assert report.ok is True
    assert [w["name"] for w in report.warnings] == ["servis:tunnel"]
    written = json.loads((tmp_path / "config" / "health-report.json").read_text(encoding="utf-8"))
    assert written["ok"] is True
    assert written["warnings"][0]["name"] == "servis:tunnel"


def test_required_panel_down_marks_unhealthy(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path)
    monkeypatch.setattr(hg, "_probe", lambda url: (False, "Timeout") if ":8766" in url else (True, "HTTP 200"))
    monkeypatch.setattr(hg, "_counts", lambda runtime: {"blocked": 0})

    report = hg.check(runtime, fix=False)

    assert report.ok is False
    assert any(check["name"] == "servis:panel" and check["required"] for check in report.checks)
