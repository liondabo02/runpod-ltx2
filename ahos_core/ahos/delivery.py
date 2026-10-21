"""Filesystem-level delivery evidence for autonomous missions.

The worker's own summary is a *claim*. This module measures what actually
changed on disk between two moments, so a mission that only wrote prose cannot
be recorded as a delivery. It is deliberately cheap: size + mtime per file,
no content hashing, hard caps on file count.
"""

from __future__ import annotations

import os
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

# Runtime chatter is not a delivery. Another process (or the project itself)
# writing logs, databases or scratch state must never be counted as work the
# mission produced, otherwise a blocked mission looks successful.
VOLATILE_PARTS = {
    "logs",
    "log",
    "tmp",
    "temp",
    "cache",
    ".cache",
    "data",
    ".storage",
}
VOLATILE_SUFFIXES = (
    ".log",
    ".sqlite3",
    ".sqlite3-wal",
    ".sqlite3-shm",
    ".db",
    ".db-wal",
    ".db-shm",
    ".pid",
    ".tmp",
    ".pyc",
)


def _is_volatile(relative) -> bool:
    if any(part in VOLATILE_PARTS for part in relative.parts[:-1]):
        return True
    return relative.name.lower().endswith(VOLATILE_SUFFIXES)


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
    skip_parts = IGNORED_PARTS | VOLATILE_PARTS
    for dirpath, dirnames, filenames in os.walk(base):
        # Klasörleri yürürken buda: node_modules/data gibi ağaçlar hiç gezilmez.
        dirnames[:] = [
            name for name in dirnames if name not in skip_parts and not name.startswith(".")
        ]
        for name in filenames:
            path = Path(dirpath) / name
            try:
                relative = path.relative_to(base)
            except ValueError:  # pragma: no cover - defensive
                continue
            if _is_volatile(relative):
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
        if truncated:
            break
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
