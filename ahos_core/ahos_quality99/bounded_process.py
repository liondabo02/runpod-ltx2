from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import signal
import subprocess
import time
from typing import Callable, Sequence


@dataclass(frozen=True, slots=True)
class BoundedProcessResult:
    returncode: int | None
    stdout: str
    stderr: str
    timed_out: bool
    cancelled: bool
    elapsed_seconds: float


class BoundedProcessRunner:
    """Run a local child with timeout and cooperative cancellation.

    The runner is zero-cost and local-only. It starts a new process group so a
    timeout/cancel can terminate the child tree instead of leaving a stuck
    terminal process behind.
    """

    def __init__(
        self,
        *,
        timeout_seconds: float,
        poll_seconds: float = 0.05,
        terminate_grace_seconds: float = 2.0,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if not 0.01 <= poll_seconds <= 5:
            raise ValueError("poll_seconds must be in [0.01, 5]")
        if terminate_grace_seconds < 0:
            raise ValueError("terminate_grace_seconds must be nonnegative")
        self.timeout_seconds = float(timeout_seconds)
        self.poll_seconds = float(poll_seconds)
        self.terminate_grace_seconds = float(terminate_grace_seconds)

    def run(
        self,
        command: Sequence[str],
        *,
        cwd: str | Path,
        stdin_text: str = "",
        cancel_requested: Callable[[], bool] | None = None,
    ) -> BoundedProcessResult:
        if not command or not all(isinstance(item, str) and item for item in command):
            raise ValueError("command must be a non-empty argv sequence")
        root = Path(cwd)
        if not root.is_dir():
            raise ValueError("cwd must exist and be a directory")

        kwargs: dict[str, object] = {}
        if os.name == "nt":
            kwargs["creationflags"] = (
                getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                | getattr(subprocess, "CREATE_NO_WINDOW", 0)
            )
        else:
            kwargs["start_new_session"] = True

        started = time.monotonic()
        process = subprocess.Popen(
            list(command),
            cwd=root,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            **kwargs,
        )
        if process.stdin is not None:
            try:
                process.stdin.write(stdin_text)
                process.stdin.close()
            except (BrokenPipeError, OSError):
                pass

        timed_out = False
        cancelled = False
        while process.poll() is None:
            if cancel_requested is not None and cancel_requested():
                cancelled = True
                self._terminate_tree(process)
                break
            if time.monotonic() - started >= self.timeout_seconds:
                timed_out = True
                self._terminate_tree(process)
                break
            time.sleep(self.poll_seconds)

        try:
            stdout, stderr = process.communicate(timeout=max(self.terminate_grace_seconds, 0.1))
        except subprocess.TimeoutExpired:
            self._kill_tree(process)
            stdout, stderr = process.communicate()

        return BoundedProcessResult(
            returncode=process.returncode,
            stdout=stdout or "",
            stderr=stderr or "",
            timed_out=timed_out,
            cancelled=cancelled,
            elapsed_seconds=round(time.monotonic() - started, 6),
        )

    def _terminate_tree(self, process: subprocess.Popen[str]) -> None:
        if process.poll() is not None:
            return
        try:
            if os.name == "nt":
                process.send_signal(getattr(signal, "CTRL_BREAK_EVENT", signal.SIGTERM))
            else:
                os.killpg(process.pid, signal.SIGTERM)
        except (ProcessLookupError, OSError, ValueError):
            try:
                process.terminate()
            except OSError:
                return

        deadline = time.monotonic() + self.terminate_grace_seconds
        while process.poll() is None and time.monotonic() < deadline:
            time.sleep(min(self.poll_seconds, 0.05))
        if process.poll() is None:
            self._kill_tree(process)

    @staticmethod
    def _kill_tree(process: subprocess.Popen[str]) -> None:
        if process.poll() is not None:
            return
        try:
            if os.name == "nt":
                # taskkill is a local OS primitive; /T includes descendants.
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    capture_output=True,
                    check=False,
                    timeout=5,
                )
            else:
                os.killpg(process.pid, signal.SIGKILL)
        except (ProcessLookupError, OSError, subprocess.TimeoutExpired):
            try:
                process.kill()
            except OSError:
                pass
