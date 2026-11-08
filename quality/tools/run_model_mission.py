"""Run one owner-style mission against the live runtime.

Usage:
    python quality/tools/run_model_mission.py "Mipiluna ..."

Loads runtime/model.env (so the remote free model is used), routes the command
through the owner console, then prints a compact result.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ahos_core"))

from ahos.daemon import _load_model_env  # noqa: E402
from ahos.owner_console import build_default_console  # noqa: E402


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    objective = " ".join(sys.argv[1:]).strip()
    if not objective:
        print("kullanım: run_model_mission.py \"görev metni\"")
        return 2

    runtime = ROOT / "ahos_core" / "runtime"
    _load_model_env(runtime)
    console = build_default_console(runtime)
    result = console.handle(objective)

    print("status:", result.status)
    print("msg:", (result.message or "")[:400])
    if result.mission is not None:
        print("mission:", result.mission.mission_id, result.mission.status.value)
        for step in result.mission.steps:
            print(
                " step", step.step.step_id, step.stage.value,
                "|", (step.worker_summary or "")[:180],
            )
    return 0 if result.status == "routed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
