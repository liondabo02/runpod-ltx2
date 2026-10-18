"""Filesystem-level delivery evidence for autonomous missions.

The worker's own summary is a *claim*. This module measures what actually
changed on disk between two moments, so a mission that only wrote prose cannot
be recorded as a delivery. It is deliberately cheap: size + mtime per file,
no content hashing, hard caps on file count.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping

IGNORED_PARTS = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "build",
    "dist",
    ".gradle",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "coverage",
    ".next",
    ".turbo",
}

MAX_FILES = 3000
MAX_LISTED = 25


@dataclass(frozen=True)
class TreeSnapshot:
    root: str
    files: Mapping[str, tuple[int, int]] = field(default_factory=dict)
    truncated: bool = False

    @property
    def count(self) -> int:
        return len(self.files)


@dataclass(frozen=True)
class TreeDiff:
    root: str
    added: tuple[str, ...] = ()
    removed: tuple[str, ...] = ()
    modified: tuple[str, ...] = ()

    @property
    def changed(self) -> int:
        return len(self.added) + len(self.removed) + len(self.modified)

    def to_dict(self) -> dict[str, object]:
        return {
            "root": self.root,
            "added": list(self.added[:MAX_LISTED]),
            "removed": list(self.removed[:MAX_LISTED]),
            "modified": list(self.modified[:MAX_LISTED]),
            "changed": self.changed,
        }


def snapshot_tree(root: str | Path, *, max_files: int = MAX_FILES) -> TreeSnapshot:
    """Cheap inventory of a project tree (size + mtime)."""

    base = Path(root)
    files: dict[str, tuple[int, int]] = {}
    if not base.is_dir():
        return TreeSnapshot(root=str(base))
    truncated = False
    for path in base.rglob("*"):
        try:
            relative = path.relative_to(base)
        except ValueError:  # pragma: no cover - defensive
            continue
        if any(part in IGNORED_PARTS for part in relative.parts):
            continue
        if path.is_symlink() or not path.is_file():
            continue
        if len(files) >= max_files:
            truncated = True
            break
        try:
            stat = path.stat()
        except OSError:
            continue
        files[relative.as_posix()] = (stat.st_size, stat.st_mtime_ns)
    return TreeSnapshot(root=str(base), files=files, truncated=truncated)


def diff_trees(before: TreeSnapshot, after: TreeSnapshot) -> TreeDiff:
    added = tuple(sorted(set(after.files) - set(before.files)))
    removed = tuple(sorted(set(before.files) - set(after.files)))
    modified = tuple(
        sorted(
            name
            for name in set(before.files) & set(after.files)
            if before.files[name] != after.files[name]
        )
    )
    return TreeDiff(
        root=after.root or before.root,
        added=added,
        removed=removed,
        modified=modified,
    )


class DeliveryTracker:
    """Snapshot the bound projects around one mission and describe the delta."""

    def __init__(self, project_roots: Iterable[str | Path] | None = None) -> None:
        self._roots = tuple(str(Path(root)) for root in (project_roots or ()))

    def roots(self) -> tuple[str, ...]:
        return self._roots

    def snapshot(self) -> dict[str, TreeSnapshot]:
        return {root: snapshot_tree(root) for root in self._roots}

    def diff(
        self, before: dict[str, TreeSnapshot], after: dict[str, TreeSnapshot]
    ) -> dict[str, object]:
        diffs = [
            diff_trees(before[root], after[root])
            for root in self._roots
            if root in before and root in after
        ]
        changed = sum(item.changed for item in diffs)
        return {
            "changed_files": changed,
            "projects": [item.to_dict() for item in diffs],
        }
