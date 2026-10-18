from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Mapping

from .company_service import CompanyService


class _MonitorLoop:
    """Do not claim company missions until a real orchestrator is configured."""

    def run_once(self) -> None:
        return None


def _read_config(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    # Windows PowerShell 5.1 may prefix JSON written with ``-Encoding utf8``
    # with a BOM. Accept it while keeping ordinary UTF-8 files unchanged.
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError("company service config must contain a JSON object")
    return value


def _coding_step(runtime_dir: Path, config: Mapping[str, object]):
    raw = config.get("coding_supervisor")
    if not isinstance(raw, Mapping) or raw.get("enabled") is not True:
        return lambda: "coding:disabled"

    builder = raw.get("builder_command")
    allowed = raw.get("allowed_test_executables")
    if not isinstance(builder, list) or not builder or not all(isinstance(x, str) and x for x in builder):
        raise ValueError("enabled coding supervisor requires builder_command argv")
    if not isinstance(allowed, list) or not allowed or not all(isinstance(x, str) and x for x in allowed):
        raise ValueError("enabled coding supervisor requires allowed_test_executables")
    queue = Path(str(raw.get("queue") or runtime_dir / "coding-supervisor-queue.json"))
    workspace = Path(str(raw.get("workspace") or runtime_dir / "coding-worktrees"))
    worker_id = str(raw.get("worker_id") or "dev-01").strip()
    timeout = int(raw.get("timeout_seconds") or 1800)
    if not worker_id or timeout < 1:
        raise ValueError("invalid coding worker_id or timeout_seconds")

    command = [
        sys.executable, "-m", "ahos.coding_supervisor",
        "--queue", str(queue), "run-once",
        "--workspace", str(workspace), "--worker-id", worker_id,
        # Encode the nested argv as one value. Builder options such as
        # ``--model`` must not be parsed as coding-supervisor options.
        "--builder-command-json", json.dumps(builder),
    ]
    for executable in allowed:
        command.extend(("--allow-test-executable", executable))
    sandbox_image = raw.get("sandbox_image")
    if sandbox_image is not None:
        if not isinstance(sandbox_image, str) or not sandbox_image.strip():
            raise ValueError("sandbox_image must be a pinned local image digest")
        sandbox_timeout = raw.get("sandbox_timeout_seconds", 300)
        if type(sandbox_timeout) is not int or not 1 <= sandbox_timeout <= 900:
            raise ValueError("sandbox_timeout_seconds must be between 1 and 900")
        command.extend(("--sandbox-image", sandbox_image,
                        "--sandbox-timeout", str(sandbox_timeout)))

    def run() -> str:
        completed = subprocess.run(
            command, text=True, capture_output=True, timeout=timeout,
            env=os.environ.copy(), check=False,
        )
        if completed.returncode not in {0, 2}:
            detail = (completed.stderr or completed.stdout).strip()[-500:]
            raise RuntimeError(f"coding supervisor exited {completed.returncode}: {detail}")
        return "coding:polled"

    return run


def _department_step(runtime_dir: Path, config_path: Path):
    """Hot-read activation and run draft batches independently of coding."""
    active: threading.Thread | None = None
    result = "departments:disabled"
    lock = threading.Lock()

    def poll() -> str:
        nonlocal active, result
        if active is not None and active.is_alive():
            return "departments:running"
        config = _read_config(config_path)
        raw = config.get("departments")
        if not isinstance(raw, Mapping) or raw.get("enabled") is not True:
            return "departments:disabled"

        def run() -> None:
            nonlocal result
            try:
                from .department_daemon import run_batch, write_status
                write_status(runtime_dir, {"status": "running"})
                status = run_batch(runtime_dir, config_path)
                value = "departments:" + str(status["status"])
            except Exception as exc:
                value = "departments:error"
                status = {"status": value, "error_type": type(exc).__name__}
            from .department_daemon import write_status
            write_status(runtime_dir, status)
            with lock:
                result = value

        active = threading.Thread(target=run, name="AHOS-departments", daemon=True)
        active.start()
        with lock:
            return result if result == "departments:error" else "departments:running"

    return poll


def build_service(runtime_dir: Path, config_path: Path, poll_seconds: float) -> CompanyService:
    config = _read_config(config_path)
    department_step = _department_step(runtime_dir, config_path)

    coding_step = _coding_step(runtime_dir, config)
    brain_step = _brain_step(runtime_dir, config_path)

    def coding_with_departments() -> str:
        brain_step()
        department_step()
        return coding_step()

    return CompanyService(
        loop=_MonitorLoop(),  # type: ignore[arg-type]
        heartbeat_path=runtime_dir / "company-service-heartbeat.json",
        stop_path=runtime_dir / "company-service.stop",
        poll_seconds=poll_seconds,
        automation_steps=(coding_with_departments,),
    )


def _brain_step(runtime_dir: Path, config_path: Path):
    """Bounded independent observation; optional dispatch never bypasses review."""
    active: threading.Thread | None = None
    next_poll = 0.0

    def poll() -> str:
        nonlocal active, next_poll
        if active is not None and active.is_alive():
            return "brain:running"
        raw = _read_config(config_path).get("holding_brain", {})
        if not isinstance(raw, dict) or raw.get("enabled") is not True:
            return "brain:disabled"
        if time.monotonic() < next_poll:
            return "brain:waiting"
        next_poll = time.monotonic() + max(30, float(raw.get("interval_seconds") or 300))

        def run() -> None:
            try:
                from .holding_brain import run_brain_cycle
                run_brain_cycle(runtime_dir, runtime_dir.parent,
                                dispatch=raw.get("dispatch") is True)
                if raw.get("watch_upstream") is True:
                    from .upstream_watch import watch_upstream
                    watch_upstream(runtime_dir, runtime_dir.parent,
                                   allow_external=raw.get("allow_external") is True)
            except Exception as exc:
                # Persist the type only, never provider text or credentials.
                path = runtime_dir / "holding-brain-error.json"
                path.write_text(json.dumps({"error_type": type(exc).__name__}), encoding="utf-8")

        active = threading.Thread(target=run, name="AHOS-brain", daemon=True)
        active.start()
        return "brain:running"

    return poll


def main() -> int:
    parser = argparse.ArgumentParser(description="AHOS continuously running local service")
    parser.add_argument("--runtime-dir", required=True)
    parser.add_argument("--config")
    parser.add_argument("--poll-seconds", type=float, default=5.0)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    if args.poll_seconds <= 0:
        raise SystemExit("--poll-seconds must be positive")
    runtime = Path(args.runtime_dir).resolve()
    runtime.mkdir(parents=True, exist_ok=True)
    config = Path(args.config).resolve() if args.config else runtime / "company-service-config.json"
    from .department_daemon import service_lock
    with service_lock(runtime / "company-service.lock", "company"):
        service = build_service(runtime, config, args.poll_seconds)
        service.stop_path.unlink(missing_ok=True)
        if args.once:
            print(service.run_once())
        else:
            service.run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
