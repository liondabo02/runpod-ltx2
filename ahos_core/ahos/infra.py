"""Infrastructure department: check the holding's own machinery and repair it.

The infrastructure department is not a document writer. It watches the pieces the
holding runs on — daemon heartbeat, watchdog, factory, office viewer, model
tunnel — reports their health, and restarts what has died. Health is written to
the daemon heartbeat so the office can show it.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

STALE_SECONDS = 180


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""

    def to_dict(self) -> dict:
        return {"name": self.name, "ok": self.ok, "detail": self.detail}


@dataclass
class Report:
    checks: list[Check] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(check.ok for check in self.checks)

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "checks": [check.to_dict() for check in self.checks],
            "actions": list(self.actions),
            "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }


def _read_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _age_seconds(path: Path) -> float | None:
    try:
        return time.time() - path.stat().st_mtime
    except OSError:
        return None


def _port_open(host: str, port: int, timeout: float = 0.6) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _process_running(pattern: str) -> bool:
    """Windows/POSIX tolerant process check without extra dependencies."""

    try:
        if os.name == "nt":
            output = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"(Get-CimInstance Win32_Process | Where-Object {{ $_.CommandLine -match '{pattern}' }} | Measure-Object).Count"],
                capture_output=True, text=True, timeout=25,
            ).stdout.strip()
            return output.isdigit() and int(output) > 0
        output = subprocess.run(
            ["pgrep", "-fc", pattern], capture_output=True, text=True, timeout=15
        ).stdout.strip()
        return output.isdigit() and int(output) > 0
    except Exception:  # noqa: BLE001 - a failed check is unhealthy, not fatal
        return False


def check(runtime_dir: str | Path, *, deep: bool = False) -> Report:
    runtime = Path(runtime_dir)
    report = Report()

    daemon = _read_json(runtime / "daemon-state.json")
    heartbeat_age = _age_seconds(runtime / "daemon-state.json")
    fresh = heartbeat_age is not None and heartbeat_age < STALE_SECONDS
    report.checks.append(
        Check(
            "daemon",
            fresh and str(daemon.get("status") or "") not in {"", "stopped"},
            f"pid={daemon.get('pid')} status={daemon.get('status')} yaş={int(heartbeat_age or -1)}s",
        )
    )

    if deep:
        report.checks.append(
            Check("watchdog", _process_running("AHOS-Watchdog"), "bekçi süreci")
        )
        report.checks.append(
            Check("factory", _process_running("AHOS-Factory"), "fabrika süreci")
        )
        report.checks.append(
            Check("office", _port_open("127.0.0.1", 8799), "ofis 8799")
        )
        tunnel_required = os.environ.get("AHOS_REQUIRE_TUNNEL", "0").strip() in {"1", "true"}
        base_url = os.environ.get("AHOS_LLM_BASE_URL", "")
        if "127.0.0.1:11500" in base_url or "localhost:11500" in base_url:
            tunnel_required = True
        tunnel_open = _port_open("127.0.0.1", 11500)
        report.checks.append(
            Check(
                "tunnel",
                tunnel_open or not tunnel_required,
                f"model tüneli 11500 {'açık' if tunnel_open else 'kapalı (ücretli model kullanılıyor)'}",
            )
        )

    queue = runtime / "company-service.db"
    report.checks.append(
        Check("queue", queue.is_file(), f"kuyruk {'var' if queue.is_file() else 'yok'}")
    )
    return report


def repair(runtime_dir: str | Path, report: Report) -> list[str]:
    """Restart only what the report proved dead; never touch a healthy piece."""

    runtime = Path(runtime_dir)
    actions: list[str] = []
    broken = {item.name for item in report.checks if not item.ok}

    if "daemon" in broken:
        script = runtime.parents[1] / "control_plane_v2" / "AHOS-Daemon.ps1"
        if script.is_file():
            try:
                subprocess.Popen(
                    ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                     "-File", str(script), "-Action", "start"],
                    cwd=str(script.parent),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                actions.append("daemon yeniden başlatıldı")
            except OSError as exc:
                actions.append(f"daemon başlatılamadı: {exc}")

    if "office" in broken:
        try:
            subprocess.Popen(
                [sys.executable, "-m", "ahos.office_server", "--runtime-dir", str(runtime),
                 "--port", "8799"],
                cwd=str(runtime.parent),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            actions.append("ofis yeniden başlatıldı")
        except OSError as exc:
            actions.append(f"ofis başlatılamadı: {exc}")

    return actions


def health(runtime_dir: str | Path, *, deep: bool = False, fix: bool = False) -> Report:
    report = check(runtime_dir, deep=deep)
    if fix and not report.ok:
        report.actions = repair(runtime_dir, report)
    return report


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # pragma: no cover
        pass
    args = list(sys.argv[1:] if argv is None else argv)
    runtime = Path("runtime")
    if "--runtime-dir" in args:
        position = args.index("--runtime-dir")
        runtime = Path(args[position + 1])
    report = health(runtime, deep="--deep" in args, fix="--fix" in args)
    print(("altyapı: " + ("sağlıklı" if report.ok else "SORUNLU")))
    for item in report.checks:
        print(f"  {'✓' if item.ok else '✗'} {item.name}: {item.detail}")
    for action in report.actions:
        print(f"  → {action}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
