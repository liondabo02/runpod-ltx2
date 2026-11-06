"""External test-suite adapter (fail-closed).

Some projects ship their own test runner (for example a Vitest suite). AHOS can
use such a suite as an *additional* acceptance signal, but the adapter must never
treat "could not run" as "passed": timeouts, crashes and missing runners all
report ``unavailable``/``timeout`` and block the mission.

Child processes are started with their stdout/stderr redirected to files (pipe
capture can hang in restricted sandboxes) and the whole process tree is killed
when the wall clock expires.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CheckResult:
    status: str  # passed | failed | timeout | unavailable
    exit_code: int | None
    duration: float
    summary: str

    @property
    def passed(self) -> bool:
        return self.status == "passed"


def _kill_tree(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            text=True,
        )
    else:  # pragma: no cover - posix
        try:
            os.killpg(os.getpgid(pid), 15)
        except OSError:
            pass


def run_suite(
    command: list[str],
    *,
    cwd: str | Path,
    timeout_seconds: float = 600.0,
    env: dict[str, str] | None = None,
) -> CheckResult:
    """Run an external suite; unknown outcomes are never reported as success."""

    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="ahos-check-") as tmp:
        out_path = Path(tmp) / "stdout.txt"
        err_path = Path(tmp) / "stderr.txt"
        with out_path.open("wb") as out, err_path.open("wb") as err:
            try:
                process = subprocess.Popen(
                    command,
                    cwd=str(cwd),
                    env={**os.environ, **(env or {})},
                    stdin=subprocess.DEVNULL,
                    stdout=out,
                    stderr=err,
                    creationflags=(
                        subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
                    ),
                )
            except (OSError, ValueError) as exc:
                return CheckResult(
                    "unavailable", None, 0.0, f"runner başlatılamadı: {exc}"
                )

            try:
                exit_code = process.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                _kill_tree(process.pid)
                process.wait(timeout=30)
                duration = time.monotonic() - started
                return CheckResult(
                    "timeout",
                    None,
                    round(duration, 2),
                    f"süre sınırı ({timeout_seconds:.0f}s) aşıldı; süreç ağacı durduruldu",
                )

        duration = time.monotonic() - started
        tail = _tail(out_path, err_path)
        if exit_code == 0:
            return CheckResult("passed", 0, round(duration, 2), tail)
        return CheckResult(
            "failed", exit_code, round(duration, 2), tail or "testler başarısız"
        )


def _tail(out_path: Path, err_path: Path, limit: int = 400) -> str:
    chunks: list[str] = []
    for path in (out_path, err_path):
        try:
            text = path.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            continue
        if text:
            chunks.append(text)
    combined = "\n".join(chunks)
    return combined[-limit:] if combined else ""


def vitest_command(repo: str | Path, test_file: str | None = None) -> list[str] | None:
    """Build a local Vitest invocation (no network, local binary only)."""

    root = Path(repo)
    binary = root / "node_modules" / ".bin" / ("vitest.cmd" if os.name == "nt" else "vitest")
    if not binary.exists():
        return None
    command = [str(binary), "run", "--reporter=dot"]
    if test_file:
        command.append(test_file)
    return command
