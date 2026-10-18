from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ArtifactProvenance:
    path: str
    sha256: str
    producer: str
    commit_sha: str
    parent_hashes: tuple[str, ...]


def capture_provenance(path: str | Path, *, producer: str, commit_sha: str, parent_hashes: tuple[str, ...] = ()) -> ArtifactProvenance:
    target = Path(path)
    if not target.is_file():
        raise FileNotFoundError(target)
    h = hashlib.sha256(target.read_bytes()).hexdigest()
    if not producer.strip() or not commit_sha.strip():
        raise ValueError("producer and commit_sha required")
    return ArtifactProvenance(str(target), h, producer, commit_sha, tuple(sorted(parent_hashes)))
