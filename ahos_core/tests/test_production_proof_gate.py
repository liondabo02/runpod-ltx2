from datetime import datetime, timedelta, timezone
import hashlib

import pytest

from ahos.proof_evidence import ProofEvidence, REQUIRED_PROOF_KINDS
from ahos.production_proof_gate import ProductionProofGate


def _evidence(tmp_path, kind, *, commit="abc", platform="windows", passed=True, age=0):
    path = tmp_path / f"{kind}.json"
    body = f'{{"kind":"{kind}"}}'.encode()
    path.write_bytes(body)
    return ProofEvidence(
        kind=kind,
        passed=passed,
        observed_at=datetime.now(timezone.utc) - timedelta(seconds=age),
        commit_sha=commit,
        platform=platform,
        artifact_path=path.name,
        artifact_sha256=hashlib.sha256(body).hexdigest(),
        source="test",
    )


def test_complete_bundle_becomes_baseline(tmp_path):
    rows = [_evidence(tmp_path, kind) for kind in REQUIRED_PROOF_KINDS]
    gate = ProductionProofGate(max_age_seconds=60)
    report = gate.evaluate(rows, root=tmp_path)
    assert report.ready is True
    assert report.proven == REQUIRED_PROOF_KINDS
    baseline = gate.to_verification_baseline(
        report,
        extra_proofs={"holding_platform", "coding_reliability", "runtime_health", "owner_gates", "evidence"},
    )
    assert "deployment_proof" in baseline.proofs
    assert baseline.commit_sha == "abc"


def test_hash_mismatch_fails_closed(tmp_path):
    row = _evidence(tmp_path, "deployment_proof")
    (tmp_path / row.artifact_path).write_text("changed", encoding="utf-8")
    report = ProductionProofGate().evaluate([row], root=tmp_path)
    assert report.ready is False
    assert "deployment_proof:artifact_hash_mismatch" in report.blockers


def test_stale_and_mixed_commit_evidence_fails(tmp_path):
    rows = [
        _evidence(tmp_path, kind, commit="a" if index == 0 else "b", age=120)
        for index, kind in enumerate(REQUIRED_PROOF_KINDS)
    ]
    report = ProductionProofGate(max_age_seconds=60).evaluate(rows, root=tmp_path)
    assert report.ready is False
    assert "mixed_commit_evidence" in report.blockers
    assert any(blocker.endswith(":stale") for blocker in report.blockers)


def test_baseline_refuses_incomplete_bundle(tmp_path):
    report = ProductionProofGate().evaluate([
        _evidence(tmp_path, "deployment_proof")
    ], root=tmp_path)
    with pytest.raises(ValueError):
        ProductionProofGate().to_verification_baseline(report)
