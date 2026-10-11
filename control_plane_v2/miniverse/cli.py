from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from .config import Settings
from .execution import MiniverseExecutionPipeline
from .orchestrator import MiniverseOrchestrator


def main() -> None:
    parser = argparse.ArgumentParser(description="Miniverse control plane v2")
    parser.add_argument("task")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Run analyze -> OpenHands build -> QA review inside an isolated workspace.",
    )
    parser.add_argument(
        "--workspace",
        default="",
        help="Existing isolated workspace directory used only with --execute.",
    )
    args = parser.parse_args()

    settings = Settings()
    missing = settings.missing_runtime_settings()
    if missing:
        raise SystemExit("Missing runtime settings: " + ", ".join(missing))

    if not args.execute:
        result = asyncio.run(MiniverseOrchestrator(settings=settings).analyze(args.task))
        print(result)
        return

    if not args.workspace:
        raise SystemExit("--workspace is required with --execute")

    workspace = Path(args.workspace).resolve()
    result = asyncio.run(
        MiniverseExecutionPipeline(settings=settings).execute(args.task, workspace)
    )
    print("=== PREFLIGHT ===")
    print(result.preflight_report)
    print("\n=== BUILDER ===")
    print(result.builder.summary)
    print("Changed files:")
    for path in result.builder.changed_files:
        print(f"- {path}")
    print("Tests:")
    for test in result.builder.tests_run:
        print(f"- {test}")
    print(f"Estimated model cost: ${result.builder.estimated_cost_usd:.4f}")
    print("\n=== QA REVIEW ===")
    print(result.qa_report)


if __name__ == "__main__":
    main()
