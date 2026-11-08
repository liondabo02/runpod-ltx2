from __future__ import annotations

import sys
import time
from pathlib import Path

from ahos.external_checks import CheckResult, run_suite, vitest_command


def _script(tmp_path: Path, body: str) -> list[str]:
    path = tmp_path / "runner.py"
    path.write_text(body, encoding="utf-8")
    return [sys.executable, str(path)]


def test_passing_suite_is_reported_as_passed(tmp_path) -> None:
    command = _script(tmp_path, "print('ok'); raise SystemExit(0)")
    result = run_suite(command, cwd=tmp_path, timeout_seconds=30)

    assert result.status == "passed"
    assert result.exit_code == 0
    assert "ok" in result.summary


def test_failing_suite_is_not_a_pass(tmp_path) -> None:
    command = _script(tmp_path, "print('2 failed'); raise SystemExit(1)")
    result = run_suite(command, cwd=tmp_path, timeout_seconds=30)

    assert result.status == "failed"
    assert result.passed is False
    assert "2 failed" in result.summary


def test_hanging_suite_times_out_and_is_killed(tmp_path) -> None:
    command = _script(tmp_path, "import time; time.sleep(30)")
    started = time.monotonic()
    result = run_suite(command, cwd=tmp_path, timeout_seconds=1)

    assert result.status == "timeout"
    assert result.passed is False
    assert time.monotonic() - started < 20


def test_missing_runner_is_unavailable(tmp_path) -> None:
    result = run_suite(
        [str(tmp_path / "yok.exe")], cwd=tmp_path, timeout_seconds=5
    )
    assert result.status == "unavailable"
    assert result.passed is False


def test_vitest_command_only_uses_local_binary(tmp_path) -> None:
    assert vitest_command(tmp_path) is None

    bin_dir = tmp_path / "node_modules" / ".bin"
    bin_dir.mkdir(parents=True)
    binary = bin_dir / ("vitest.cmd" if sys.platform == "win32" else "vitest")
    binary.write_text("", encoding="utf-8")

    command = vitest_command(tmp_path, "tests/access-gate.test.ts")
    assert command is not None
    assert "run" in command and "--reporter=dot" in command
    assert command[-1] == "tests/access-gate.test.ts"


def test_check_result_contract() -> None:
    assert CheckResult("passed", 0, 1.0, "").passed is True
    assert CheckResult("timeout", None, 1.0, "").passed is False
    assert CheckResult("unavailable", None, 0.0, "").passed is False
