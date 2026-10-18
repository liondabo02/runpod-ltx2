from datetime import datetime, timezone
import hashlib

from ahos.proof_evidence import ProofEvidence
from ahos.proof_manifest import build_manifest


def _row(kind):
    return ProofEvidence(
        kind=kind,
        passed=True,
        observed_at=datetime(2026, 10, 18, tzinfo=timezone.utc),
        commit_sha="abc",
        platform="windows",
        artifact_path=f"{kind}.json",
        artifact_sha256=hashlib.sha256(kind.encode()).hexdigest(),
        source="test",
    )


def test_proof_manifest_is_deterministic():
    a = build_manifest([_row("deployment_proof"), _row("recovery_proof")])
    b = build_manifest([_row("recovery_proof"), _row("deployment_proof")])
    assert a.manifest_sha256 == b.manifest_sha256
    assert len(a.manifest_sha256) == 64
