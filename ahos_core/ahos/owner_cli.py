from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .owner_console import build_default_console


def _default_runtime_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "runtime"


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # pragma: no cover - non-reconfigurable stream
        pass

    parser = argparse.ArgumentParser(
        prog="ahos-owner",
        description="Tek satırlık sahip komutu: departman kur, iş ver, durum sor.",
    )
    parser.add_argument(
        "command",
        nargs="*",
        help="ör. 'çizgi film departmanı kur' veya 'landing page yap'",
    )
    parser.add_argument(
        "--runtime-dir",
        default=str(_default_runtime_dir()),
        help="departman defteri ve artefaktların tutulacağı dizin",
    )
    args = parser.parse_args(argv)

    runtime_dir = Path(args.runtime_dir)
    runtime_dir.mkdir(parents=True, exist_ok=True)

    console = build_default_console(runtime_dir)
    text = " ".join(args.command).strip() or "durum"
    result = console.handle(text)

    print(result.message)
    if result.mission is not None:
        print(f"\nGörev durumu: {result.mission.status.value}")
        for step in result.mission.steps:
            print(f"  - {step.step.step_id}: {step.stage.value} ({step.reason})")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
