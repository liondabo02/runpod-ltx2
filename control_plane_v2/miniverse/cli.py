from __future__ import annotations

import argparse
import asyncio

from .config import Settings
from .orchestrator import MiniverseOrchestrator


def main() -> None:
    parser = argparse.ArgumentParser(description="Miniverse control plane v2")
    parser.add_argument("task")
    args = parser.parse_args()

    settings = Settings()
    missing = settings.missing_runtime_settings()
    if missing:
        raise SystemExit("Missing runtime settings: " + ", ".join(missing))

    result = asyncio.run(MiniverseOrchestrator(settings=settings).analyze(args.task))
    print(result)


if __name__ == "__main__":
    main()
