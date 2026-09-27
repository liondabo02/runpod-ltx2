from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
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
    value = json.loads(path.read_text(encoding="utf-8"))
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
        "--builder-command", *builder,
    ]
    for executable in allowed:
        command.extend(("--allow-test-executable", executable))

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


def build_service(runtime_dir: Path, config_path: Path, poll_seconds: float) -> CompanyService:
    config = _read_config(config_path)
    return CompanyService(
        loop=_MonitorLoop(),  # type: ignore[arg-type]
        heartbeat_path=runtime_dir / "company-service-heartbeat.json",
        stop_path=runtime_dir / "company-service.stop",
        poll_seconds=poll_seconds,
        automation_steps=(_coding_step(runtime_dir, config),),
    )


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
    service = build_service(runtime, config, args.poll_seconds)
    service.stop_path.unlink(missing_ok=True)
    if args.once:
        print(service.run_once())
    else:
        service.run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
