from pathlib import Path

import ahos


def test_repository_root_test_entrypoint_exists():
    root = Path(__file__).resolve().parents[2]
    entry = root / "ahos_core" / "run_tests.py"
    assert entry.is_file()
    assert ahos.__file__
