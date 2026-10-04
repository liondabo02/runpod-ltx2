"""Independent department service; does not stop or alter the coding daemon."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
import os
import uuid
from datetime import datetime, timezone
from contextlib import contextmanager

from .company_daemon import _read_config
from .department_company import build_persistent_department_loop, reconcile_department_missions
from .department_provider import DepartmentProviderConfig, build_department_generator
from .department_runtime import DepartmentRuntime


def run_batch(runtime_dir: Path, config_path: Path) -> dict:
    raw = _read_config(config_path).get("departments", {})
    if not isinstance(raw, dict) or raw.get("enabled") is not True:
        return {"status": "disabled"}
    generator = build_department_generator(DepartmentProviderConfig(
        allow_external=raw.get("allow_external") is True,
        model_id=str(raw.get("model") or "openrouter/free"),
        timeout_seconds=float(raw.get("timeout_seconds") or 90),
    ))
    runtime = DepartmentRuntime(runtime_dir / "departments", generator,
                                max_workers=int(raw.get("max_workers") or 3))
    runtime.recover_interrupted()
    loop = build_persistent_department_loop(runtime_dir, runtime)
    reconcile_department_missions(loop, runtime)
    # Production in the shared draft queue remains independently scheduled.
    mission = loop.run_once()
    snapshot = runtime.run_once()
    return {"status": "polled", "counts": snapshot["counts"],
            "mission_id": mission.mission_id if mission else None}


@contextmanager
def service_lock(path: Path):
    """OS-held singleton lock, released even after process termination."""
    with path.open("a+b") as handle:
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise RuntimeError("department service is already running") from exc
        try:
            yield
        finally:
            if os.name == "nt":
                import msvcrt
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def write_status(root: Path, result: dict) -> None:
    payload = {**result, "timestamp": datetime.now(timezone.utc).isoformat(), "pid": os.getpid()}
    path = root / "department-service-status.json"
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temp.write_text(json.dumps(payload), encoding="utf-8")
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-dir", required=True)
    parser.add_argument("--config")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-seconds", type=float, default=5)
    args = parser.parse_args()
    if args.poll_seconds <= 0:
        parser.error("poll seconds must be positive")
    root = Path(args.runtime_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    config = Path(args.config) if args.config else root / "company-service-config.json"
    with service_lock(root / "department-service.lock"):
        while not any((root / name).exists() for name in
                      ("department-service.stop", "company-service.stop")):
            write_status(root, {"status": "running"})
            try:
                result = run_batch(root, config)
            except Exception as exc:
                result = {"status": "error", "error_type": type(exc).__name__}
            write_status(root, result)
            if args.once:
                print(json.dumps(result))
                return 0 if result["status"] != "error" else 2
            time.sleep(args.poll_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
