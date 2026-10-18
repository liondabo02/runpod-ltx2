from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import time


@dataclass(frozen=True, slots=True)
class CompanyServiceRestartReport:
    first_heartbeat_seen: bool
    first_stop_clean: bool
    second_heartbeat_seen: bool
    second_stop_clean: bool
    timestamp_advanced: bool
    passed: bool


_CHILD = r'''
from pathlib import Path
import sys
from ahos.company_service import CompanyService

class IdleLoop:
    def run_once(self):
        return None

root = Path(sys.argv[1])
service = CompanyService(
    loop=IdleLoop(),
    heartbeat_path=root / "company-service-heartbeat.json",
    stop_path=root / "company-service.stop",
    poll_seconds=0.05,
)
service.run_forever()
'''


def _wait_heartbeat(path: Path, *, timeout_seconds: float = 3.0) -> dict[str, object] | None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if path.is_file():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                if payload.get("state") in {"starting", "polling", "idle", "processed"}:
                    return payload
            except (OSError, json.JSONDecodeError):
                pass
        time.sleep(0.03)
    return None


def _run_cycle(root: Path, package_root: Path) -> tuple[dict[str, object] | None, bool]:
    stop = root / "company-service.stop"
    stop.unlink(missing_ok=True)
    process = subprocess.Popen(
        [sys.executable, "-c", _CHILD, str(root)],
        cwd=package_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    heartbeat = _wait_heartbeat(root / "company-service-heartbeat.json")
    stop.write_text("quality99 isolated stop", encoding="utf-8")
    try:
        process.wait(timeout=4)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=2)
        return heartbeat, False
    return heartbeat, process.returncode == 0


def run_company_service_restart_e2e() -> CompanyServiceRestartReport:
    package_root = Path(__file__).resolve().parents[1]
    with TemporaryDirectory(prefix="ahos-q99-company-service-") as tmp:
        root = Path(tmp)
        first, first_stop = _run_cycle(root, package_root)
        first_timestamp = str((first or {}).get("timestamp") or "")
        time.sleep(0.05)
        second, second_stop = _run_cycle(root, package_root)
        second_timestamp = str((second or {}).get("timestamp") or "")
        advanced = bool(first_timestamp and second_timestamp and second_timestamp > first_timestamp)
        passed = bool(first and second and first_stop and second_stop and advanced)
        return CompanyServiceRestartReport(
            first_heartbeat_seen=first is not None,
            first_stop_clean=first_stop,
            second_heartbeat_seen=second is not None,
            second_stop_clean=second_stop,
            timestamp_advanced=advanced,
            passed=passed,
        )
