"""File-based bridge between AHOS and a Ruflo worker process.

Why a file bridge: Ruflo is a Node CLI whose agent execution spawns Claude Code.
Starting it from inside AHOS' own process tree proved unreliable in restricted
sandboxes, so AHOS *submits* a request file and a small watcher process (started
once, outside the agent sandbox) executes it and writes the result back.

Contract
--------
request  ``runtime/ruflo-queue/<mission_id>.json``
         ``{"mission_id", "prompt", "project", "timeout_seconds"}``
result   ``runtime/ruflo-results/<mission_id>.json``
         ``{"status": "completed"|"failed", "exit_code", "seconds", "log"}``
"""

from __future__ import annotations

import json
import time
from pathlib import Path


def queue_dir(runtime_dir: str | Path) -> Path:
    return Path(runtime_dir) / "ruflo-queue"


def results_dir(runtime_dir: str | Path) -> Path:
    return Path(runtime_dir) / "ruflo-results"


def submit(
    runtime_dir: str | Path,
    *,
    mission_id: str,
    prompt: str,
    project: str,
    timeout_seconds: float = 180.0,
) -> Path:
    target = queue_dir(runtime_dir)
    target.mkdir(parents=True, exist_ok=True)
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in mission_id)[:80]
    path = target / f"{safe}.json"
    payload = {
        "mission_id": mission_id,
        "prompt": prompt,
        "project": project,
        "timeout_seconds": timeout_seconds,
        "submitted_at": time.time(),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def read_result(
    runtime_dir: str | Path, mission_id: str
) -> dict[str, object] | None:
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in mission_id)[:80]
    path = results_dir(runtime_dir) / f"{safe}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def wait_for_result(
    runtime_dir: str | Path,
    mission_id: str,
    *,
    timeout_seconds: float = 240.0,
    poll_seconds: float = 1.0,
    sleep=time.sleep,
    clock=time.monotonic,
) -> dict[str, object] | None:
    """Bounded wait; returns None when the worker did not answer in time."""

    deadline = clock() + max(1.0, timeout_seconds)
    attempts = 0
    max_attempts = 10_000
    while clock() < deadline and attempts < max_attempts:
        result = read_result(runtime_dir, mission_id)
        if result is not None:
            return result
        attempts += 1
        sleep(poll_seconds)
    return None
