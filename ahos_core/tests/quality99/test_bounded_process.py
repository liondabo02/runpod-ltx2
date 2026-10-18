from pathlib import Path
import sys

from ahos_quality99.bounded_process import BoundedProcessRunner


def test_bounded_process_completes(tmp_path):
    result = BoundedProcessRunner(timeout_seconds=2).run(
        [sys.executable, "-c", "print('ok')"],
        cwd=tmp_path,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "ok"
    assert result.timed_out is False
    assert result.cancelled is False


def test_bounded_process_times_out(tmp_path):
    result = BoundedProcessRunner(
        timeout_seconds=0.15,
        poll_seconds=0.02,
        terminate_grace_seconds=0.1,
    ).run(
        [sys.executable, "-c", "import time; time.sleep(10)"],
        cwd=tmp_path,
    )
    assert result.timed_out is True
    assert result.cancelled is False
    assert result.elapsed_seconds < 3


def test_bounded_process_cancels(tmp_path):
    calls = {"n": 0}

    def cancelled():
        calls["n"] += 1
        return calls["n"] >= 3

    result = BoundedProcessRunner(
        timeout_seconds=5,
        poll_seconds=0.02,
        terminate_grace_seconds=0.1,
    ).run(
        [sys.executable, "-c", "import time; time.sleep(10)"],
        cwd=tmp_path,
        cancel_requested=cancelled,
    )
    assert result.cancelled is True
    assert result.timed_out is False
    assert result.elapsed_seconds < 3
