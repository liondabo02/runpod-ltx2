"""Untracked local imports must not silently ship as a 'ready' Git release."""

from __future__ import annotations

import subprocess
from pathlib import Path

from ahos.source_integrity import missing_tracked_imports


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def test_untracked_import_used_by_tracked_code_blocks_release(tmp_path):
    repo = tmp_path / "repo"
    package = repo / "ahos_core" / "ahos"
    package.mkdir(parents=True)
    _git(repo, "init", "-q")
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "ceo.py").write_text(
        "from .studio_department import matches\n", encoding="utf-8"
    )
    _git(repo, "add", "ahos_core/ahos/__init__.py", "ahos_core/ahos/ceo.py")
    # A clean checkout must fail before any local-only copy exists.
    assert missing_tracked_imports(repo) == ("ahos_core/ahos/studio_department",)
    (package / "studio_department.py").write_text(
        "def matches(): return True\n", encoding="utf-8"
    )
    assert missing_tracked_imports(repo) == ("ahos_core/ahos/studio_department",)

    _git(repo, "add", "ahos_core/ahos/studio_department.py")
    assert missing_tracked_imports(repo) == ()


def test_absolute_ahos_import_is_checked(tmp_path):
    repo = tmp_path / "repo"
    package = repo / "ahos_core" / "ahos"
    package.mkdir(parents=True)
    _git(repo, "init", "-q")
    (package / "worker.py").write_text(
        "from ahos.providers import choose_chain\n", encoding="utf-8"
    )
    _git(repo, "add", "ahos_core/ahos/worker.py")
    (package / "providers.py").write_text("choose_chain = None", encoding="utf-8")
    assert missing_tracked_imports(repo) == ("ahos_core/ahos/providers",)


def test_missing_nonexistent_import_is_not_falsely_classified_as_untracked(tmp_path):
    """ImportError is a separate test failure; this audit checks provenance."""
    repo = tmp_path / "repo"
    package = repo / "ahos_core" / "ahos"
    package.mkdir(parents=True)
    _git(repo, "init", "-q")
    (package / "ceo.py").write_text("from . import OPTIONAL_FLAG\n", encoding="utf-8")
    _git(repo, "add", "ahos_core/ahos/ceo.py")
    assert missing_tracked_imports(repo) == ()
