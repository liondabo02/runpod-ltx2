import hashlib
import json
import os
from pathlib import Path
import sys
import pytest
from ahos.upstream_tool_bridge import PINS, ToolBridgeError, _bounded_run, run_tool


def registry(tmp_path):
    source = tmp_path / "cli.py"
    source.write_text("reviewed", encoding="utf-8")
    return {"schema": "ahos.upstream-tools.v1", "tools": {
        name: {"source_url": url, "source_commit": commit, "license": "MIT", "executable": sys.executable,
               "entrypoint": str(source), "entrypoint_sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
        for name, (url, commit) in PINS.items()}}


def test_bridge_fixed_read_only_commands(monkeypatch, tmp_path):
    calls = []
    def runner(command, timeout, limit, home):
        calls.append(command)
        assert home.is_dir()
        return {"exit_code": 0, "stdout": "{}", "stderr": "", "timed_out": False, "output_truncated": False}
    monkeypatch.setattr("ahos.upstream_tool_bridge._bounded_run", runner)
    data = registry(tmp_path)
    result = run_tool(data, "hn-search", query="sqlite --allow-writes", allow_external=True)
    assert calls[0][-4:] == ["call", "hacker-news", "search", "query=sqlite --allow-writes"]
    assert "--allow-writes" not in calls[0]
    assert result["source_commit"] == PINS["api_anything"][1]
    assert result["kind"] == "public_search"
    result = run_tool(data, "reach-doctor", allow_external=True)
    assert calls[1][-3:] == ["-m", "agent_reach.cli", "doctor"]
    assert result["kind"] == "installation_diagnostics"


def test_bridge_blocks_unreviewed_sources_and_entrypoint_changes(tmp_path):
    data = registry(tmp_path)
    with pytest.raises(ToolBridgeError):
        run_tool(data, "hn-search", query="sqlite")
    with pytest.raises(ToolBridgeError):
        run_tool(data, "install", allow_external=True)
    data["tools"]["api_anything"]["source_commit"] = "0" * 40
    with pytest.raises(ToolBridgeError):
        run_tool(data, "hn-search", query="sqlite", allow_external=True)
    data = registry(tmp_path)
    Path(data["tools"]["api_anything"]["entrypoint"]).write_text("changed")
    with pytest.raises(ToolBridgeError):
        run_tool(data, "hn-search", query="sqlite", allow_external=True)


def test_bounded_runner_strips_secrets_and_user_home(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENROUTER_API_KEY", "secret")
    monkeypatch.setenv("HTTP_PROXY", "credential")
    script = "import os,json; print(json.dumps({'key':os.getenv('OPENROUTER_API_KEY'),'proxy':os.getenv('HTTP_PROXY'),'home':os.getenv('HOME')}))"
    result = _bounded_run([sys.executable, "-c", script], 5, 1024, tmp_path)
    assert result["exit_code"] == 0
    assert json.loads(result["stdout"]) == {"key": None, "proxy": None, "home": str(tmp_path)}


def test_output_bounds_and_timeout(tmp_path):
    result = _bounded_run([sys.executable, "-c", "print('x'*100000)"], 5, 1024, tmp_path)
    assert result["output_truncated"] and len(result["stdout"]) == 1024
    result = _bounded_run([sys.executable, "-c", "import time;time.sleep(30)"], 1, 1024, tmp_path)
    assert result["timed_out"] and result["exit_code"] != 0
