"""Acceptance gate for the holding's own source tree.

Runs a fast, deterministic slice of the test suite. It is intentionally bounded
(under two minutes) so an autonomous worker can use it as a gate before touching
the holding's code: a patch that breaks these tests is rejected and reverted.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "ahos_core"

SUITE = (
    "tests/test_delivery_verdict.py",
    "tests/test_outbox_executor.py",
    "tests/test_ideas.py",
    "tests/test_failure_analytics.py",
    "tests/test_company_foundry.py",
    "tests/test_pwa_shell.py",
)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # pragma: no cover
        pass
    import os

    env = dict(os.environ)
    env["PYTHONPATH"] = str(CORE)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-x", *SUITE],
        cwd=str(CORE),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=110,
        env=env,
    )
    output = (completed.stdout or "") + (completed.stderr or "")
    tail = output.strip().splitlines()[-1] if output.strip() else "(çıktı yok)"
    print(("Kabul kapısı: " + ("temiz" if completed.returncode == 0 else "DÜŞTÜ")) + " — " + tail)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
