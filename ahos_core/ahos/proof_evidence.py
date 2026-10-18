from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


REQUIRED_PROOF_KINDS = frozenset({
    "deployment_proof",
    "autonomous_runtime_proof",
    "recovery_proof",
    "studio_acceptance",
    "identity_acceptance",
    "language_acceptance",
})


@dataclass(frozen=True, slots=True)
class ProofEvidence:
    kind: str
    passed: bool
    observed_at: datetime
    commit_sha: str
    platform: str
    artifact_path: str
    artifact_sha256: str
    source: str
    details: str = ""

    def __post_init__(self) -> None:
        if self.kind not in REQUIRED_PROOF_KINDS:
            raise ValueError(f"unsupported proof kind: {self.kind}")
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        if not self.commit_sha.strip():
            raise ValueError("commit_sha is required")
        if not self.platform.strip():
            raise ValueError("platform is required")
        if not self.artifact_path.strip():
            raise ValueError("artifact_path is required")
        if len(self.artifact_sha256) != 64:
            raise ValueError("artifact_sha256 must be a sha256 hex digest")
        if not self.source.strip():
            raise ValueError("source is required")


def sha256_file(path: str | Path) -> str:
    target = Path(path)
    digest = hashlib.sha256()
    with target.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_artifact(evidence: ProofEvidence, *, root: str | Path = ".") -> tuple[bool, str]:
    target = (Path(root) / evidence.artifact_path).resolve()
    try:
        actual = sha256_file(target)
    except OSError:
        return False, "artifact_missing"
    if actual != evidence.artifact_sha256:
        return False, "artifact_hash_mismatch"
    return True, "verified"


def is_fresh(evidence: ProofEvidence, *, max_age_seconds: float, now: datetime | None = None) -> bool:
    if max_age_seconds <= 0:
        raise ValueError("max_age_seconds must be positive")
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    observed = evidence.observed_at.astimezone(timezone.utc)
    age = max(0.0, (current - observed).total_seconds())
    return age <= max_age_seconds
