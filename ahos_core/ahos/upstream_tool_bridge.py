"""Reviewed upstream operations only; diagnostics are not content acquisition."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import threading

PINS = {
    "api_anything": ("https://github.com/goodnight000/api-anything", "fe5cca70fe145634e49a1c9ba1f3e8250b291bea"),
    "agent_reach": ("https://github.com/Panniantong/Agent-Reach", "94f06c1969dfc1834001269d79d3ad0972d9dee6"),
}

class ToolBridgeError(ValueError):
    pass


def load_registry(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if data.get("schema") != "ahos.upstream-tools.v1":
        raise ToolBridgeError("unsupported registry schema")
    return data


def _entry(registry: dict, name: str) -> dict:
    entry = registry.get("tools", {}).get(name, {})
    url, commit = PINS[name]
    if entry.get("source_url") != url or entry.get("source_commit") != commit or entry.get("license") != "MIT":
        raise ToolBridgeError("upstream source has not been reviewed")
    executable = Path(entry.get("executable", ""))
    if not executable.is_absolute() or not executable.is_file():
        raise ToolBridgeError("installed executable is missing")
    source = Path(entry.get("entrypoint", ""))
    if not source.is_absolute() or not source.is_file():
        raise ToolBridgeError("installed entrypoint is missing")
    digest = entry.get("entrypoint_sha256", "")
    if not re.fullmatch(r"[a-f0-9]{64}", digest) or hashlib.sha256(source.read_bytes()).hexdigest() != digest:
        raise ToolBridgeError("installed entrypoint changed after registration")
    return entry


def _bounded_run(command: list[str], timeout: int, limit: int, home: Path) -> dict:
    # No API keys, proxy credentials, browser cookie directories or user config.
    env = {key: os.environ[key] for key in ("SystemRoot", "WINDIR", "COMSPEC") if key in os.environ}
    system32 = str(Path(env.get("SystemRoot", "/usr")) / "System32") if os.name == "nt" else "/usr/bin:/bin"
    env.update({"PATH": str(Path(command[0]).parent) + os.pathsep + system32,
                "HOME": str(home), "USERPROFILE": str(home), "APPDATA": str(home),
                "LOCALAPPDATA": str(home), "TEMP": str(home), "TMP": str(home),
                "API_ANYTHING_HOME": str(home), "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8"})
    captured = [bytearray(), bytearray()]
    total = [0, 0]
    process = subprocess.Popen(command, cwd=home, env=env, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    def drain(stream, index):
        while chunk := stream.read(4096):
            total[index] += len(chunk)
            captured[index].extend(chunk[:max(0, limit - len(captured[index]))])
    threads = [threading.Thread(target=drain, args=(stream, i), daemon=True)
               for i, stream in enumerate((process.stdout, process.stderr))]
    for thread in threads:
        thread.start()
    timed_out = False
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        process.kill()
        process.wait(timeout=5)
    for thread in threads:
        thread.join(timeout=5)
    if any(thread.is_alive() for thread in threads):
        raise ToolBridgeError("upstream subprocess did not close output streams")
    return {"exit_code": process.returncode, "timed_out": timed_out,
            "stdout": captured[0].decode("utf-8", errors="replace"),
            "stderr": captured[1].decode("utf-8", errors="replace"),
            "output_truncated": any(size > limit for size in total)}


def run_tool(registry: dict, operation: str, *, query: str = "", allow_external: bool = False,
             timeout: int = 45, output_limit: int = 65536) -> dict:
    if not 1 <= timeout <= 120 or not 1024 <= output_limit <= 262144:
        raise ToolBridgeError("invalid execution bounds")
    if not allow_external:
        raise ToolBridgeError("read-only external execution must be explicitly enabled")
    if operation == "hn-search":
        name = "api_anything"
        if not query.strip() or len(query) > 300 or any(ord(c) < 32 for c in query):
            raise ToolBridgeError("query must be printable text of at most 300 characters")
        entry = _entry(registry, name)
        command = [entry["executable"], entry["entrypoint"], "call", "hacker-news", "search", "query=" + query]
    elif operation == "reach-doctor":
        name = "agent_reach"
        if query:
            raise ToolBridgeError("doctor does not accept a query")
        entry = _entry(registry, name)
        command = [entry["executable"], "-m", "agent_reach.cli", "doctor"]
    else:
        raise ToolBridgeError("operation has not been reviewed")
    with tempfile.TemporaryDirectory(prefix="ahos-public-tool-") as directory:
        result = _bounded_run(command, timeout, output_limit, Path(directory))
    return {"schema": "ahos.upstream-result.v1", "operation": operation,
            "kind": "public_search" if operation == "hn-search" else "installation_diagnostics",
            "tool": name, "source_url": entry["source_url"], "source_commit": entry["source_commit"],
            "entrypoint_sha256": entry["entrypoint_sha256"], "license": entry["license"],
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "external_writes_enabled": False, "credentials_inherited": False,
            "content_is_untrusted": True, **result}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--allow-external", action="store_true")
    parser.add_argument("operation", choices=("hn-search", "reach-doctor"))
    parser.add_argument("--query", default="")
    args = parser.parse_args(argv)
    try:
        result = run_tool(load_registry(args.registry), args.operation, query=args.query,
                          allow_external=args.allow_external)
    except (ToolBridgeError, OSError, json.JSONDecodeError) as exc:
        # Never print upstream errors that may include credentials/config content.
        print(json.dumps({"status": "blocked", "error_type": type(exc).__name__}))
        return 2
    print(json.dumps(result, ensure_ascii=True))
    return 0 if result["exit_code"] == 0 and not result["timed_out"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
