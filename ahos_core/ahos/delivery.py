"""Filesystem-level delivery evidence for autonomous missions.

The worker's own summary is a *claim*. This module compares bounded SHA-256
content inventories before and after a mission: touching a file is not delivery
and same-size edits are not missed. Incomplete/unreadable scans fail closed.
Large media exceeding the hash budget need a separate artifact verifier.
"""

from __future__ import annotations

import hashlib
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
MAX_HASH_BYTES = 384 * 1024 * 1024
HASH_CHUNK_BYTES = 128 * 1024

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
    hashes: Mapping[str, str] = field(default_factory=dict)
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
    unverified: bool = False

    @property
    def changed(self) -> int:
        # Partial or unreadable snapshots are never evidence of delivery.
        return 0 if self.unverified else len(self.added) + len(self.removed) + len(self.modified)

    def to_dict(self) -> dict[str, object]:
        return {
            "root": self.root,
            "added": list(self.added[:MAX_LISTED]),
            "removed": list(self.removed[:MAX_LISTED]),
            "modified": list(self.modified[:MAX_LISTED]),
            "changed": self.changed,
            "unverified": self.unverified,
        }


def snapshot_tree(root: str | Path, *, max_files: int = MAX_FILES) -> TreeSnapshot:
    """Bounded content-hashed inventory; partial scans cannot prove delivery."""

    base = Path(root)
    files: dict[str, tuple[int, int]] = {}
    hashes: dict[str, str] = {}
    if not base.is_dir():
        return TreeSnapshot(root=str(base), truncated=True)
    truncated = False
    bytes_hashed = 0
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
                if not path.resolve().is_relative_to(base.resolve()):
                    truncated = True
                    break
                stat = path.stat()
                if bytes_hashed + stat.st_size > MAX_HASH_BYTES:
                    truncated = True
                    break
                digest = hashlib.sha256()
                with path.open("rb") as handle:
                    for chunk in iter(lambda: handle.read(HASH_CHUNK_BYTES), b""):
                        digest.update(chunk)
                stable = path.stat()
                if (stable.st_size, stable.st_mtime_ns) != (stat.st_size, stat.st_mtime_ns):
                    truncated = True
                    break
            except (OSError, ValueError):
                truncated = True
                break
            name = relative.as_posix()
            files[name] = (stat.st_size, stat.st_mtime_ns)
            hashes[name] = digest.hexdigest()
            bytes_hashed += stat.st_size
        if truncated:
            break
    return TreeSnapshot(root=str(base), files=files, hashes=hashes, truncated=truncated)


def diff_trees(before: TreeSnapshot, after: TreeSnapshot) -> TreeDiff:
    added = tuple(sorted(set(after.files) - set(before.files)))
    removed = tuple(sorted(set(before.files) - set(after.files)))
    unverified = (
        before.truncated or after.truncated
        or set(before.files) != set(before.hashes)
        or set(after.files) != set(after.hashes)
    )
    modified = tuple(sorted(
        name for name in set(before.files) & set(after.files)
        if before.hashes.get(name) != after.hashes.get(name)
    ))
    return TreeDiff(
        root=after.root or before.root,
        added=added,
        removed=removed,
        modified=modified,
        unverified=unverified,
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
            "productive_files": sum(len(item.added) + len(item.modified) for item in diffs
                                    if not item.unverified),
            "removed_files": sum(len(item.removed) for item in diffs),
            "all_verified": all(not item.unverified for item in diffs),
            "projects": [item.to_dict() for item in diffs],
        }
