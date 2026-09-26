from __future__ import annotations

import subprocess
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def _ignored(paths: list[str]) -> set[str]:
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", "--stdin"],
        cwd=REPOSITORY_ROOT,
        input="\n".join(paths) + "\n",
        capture_output=True,
        check=False,
        text=True,
    )
    # git check-ignore returns 1 when no input path is ignored. Any other
    # non-zero value is an operational error and must not be hidden.
    assert result.returncode in (0, 1), result.stderr
    return set(result.stdout.splitlines())


def test_generated_python_artifacts_are_ignored() -> None:
    generated = [
        "ahos_core/.venv/Scripts/python.exe",
        "ahos_core/ahos_core.egg-info/PKG-INFO",
        "ahos_core/ahos/__pycache__/audio.cpython-312.pyc",
        "ahos_core/.pytest_cache/v/cache/nodeids",
        "ahos_core/.coverage",
        "ahos_core/htmlcov/index.html",
        "build/lib/ahos/__init__.py",
        "dist/ahos_core-0.1.0-py3-none-any.whl",
    ]

    assert _ignored(generated) == set(generated)


def test_example_environment_files_remain_trackable() -> None:
    trackable = [
        ".env.example",
        "control_plane_v2/.env.runtime.example",
    ]

    assert _ignored(trackable) == set()
