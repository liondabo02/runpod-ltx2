from __future__ import annotations

import argparse
import asyncio

from .core import ControlPlane


def main() -> None:
    parser = argparse.ArgumentParser(description="Miniverse multi-agent control plane")
    parser.add_argument("task", help="Task for the agent team")
    parser.add_argument("--context", default="", help="Shared context for all agents")
    args = parser.parse_args()

    result = asyncio.run(ControlPlane().execute(args.task, args.context))
    print(result)


if __name__ == "__main__":
    main()
