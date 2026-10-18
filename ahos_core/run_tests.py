from __future__ import annotations

import sys
from pathlib import Path


def repository_root() -> Path:
    return Path(__file__).resolve().parent.parent


def main(argv: list[str] | None = None) -> int:
    core = Path(__file__).resolve().parent
    if str(core) not in sys.path:
        sys.path.insert(0, str(core))
    import pytest
    args = list(argv if argv is not None else sys.argv[1:])
    if not args:
        args = [str(core / "tests"), "-q"]
    return int(pytest.main(args))


if __name__ == "__main__":
    raise SystemExit(main())
