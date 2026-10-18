from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import time


@dataclass(frozen=True, slots=True)
class SoakReport:
    duration_seconds: float
    samples: int
    unique_timestamps: int
    error_states: int
    max_gap_seconds: float
    clean_stop: bool
    passed: bool


_CHILD = r'''
from pathlib import Path
import sys
from ahos.company_service import CompanyService

class IdleLoop:
    def run_once(self):
        return None

root = Path(sys.argv[1])
CompanyService(
    loop=IdleLoop(),
    heartbeat_path=root / "company-service-heartbeat.json",
    stop_path=root / "company-service.stop",
    poll_seconds=0.05,
).run_forever()
'''


def run_company_service_soak(*, duration_seconds: float = 10.0) -> SoakReport:
    """Bounded real CompanyService soak in an isolated temporary runtime."""
    if not 1.0 <= duration_seconds <= 120.0:
        raise ValueError("duration_seconds must be in [1,120]")
    package_root = Path(__file__).resolve().parents[1]
    with TemporaryDirectory(prefix="ahos-q99-soak-") as tmp:
        root = Path(tmp)
        heartbeat_path = root / "company-service-heartbeat.json"
        stop_path = root / "company-service.stop"
        process = subprocess.Popen(
            [sys.executable, "-c", _CHILD, str(root)],
            cwd=package_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        end = time.monotonic() + duration_seconds
        rows: list[tuple[float, str, str]] = []
        seen_payload = ""
        while time.monotonic() < end:
            if heartbeat_path.is_file():
                try:
                    raw = heartbeat_path.read_text(encoding="utf-8")
                    payload = json.loads(raw)
                    fingerprint = raw
                    if fingerprint != seen_payload:
                        rows.append((
                            time.monotonic(),
                            str(payload.get("timestamp") or ""),
                            str(payload.get("state") or ""),
                        ))
                        seen_payload = fingerprint
                except (OSError, json.JSONDecodeError):
                    pass
            if process.poll() is not None:
                break
            time.sleep(0.03)

        stop_path.write_text("quality99 bounded soak stop", encoding="utf-8")
        try:
            process.wait(timeout=4)
            clean = process.returncode == 0
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)
            clean = False

        error_states = sum(state == "error" for _, _, state in rows)
        unique_timestamps = len({ts for _, ts, _ in rows if ts})
        gaps = [
            right[0] - left[0]
            for left, right in zip(rows, rows[1:])
        ]
        max_gap = max(gaps, default=0.0)
        passed = (
            clean
            and error_states == 0
            and unique_timestamps >= max(5, int(duration_seconds))
            and max_gap <= 1.0
        )
        return SoakReport(
            duration_seconds=duration_seconds,
            samples=len(rows),
            unique_timestamps=unique_timestamps,
            error_states=error_states,
            max_gap_seconds=round(max_gap, 3),
            clean_stop=clean,
            passed=passed,
        )
