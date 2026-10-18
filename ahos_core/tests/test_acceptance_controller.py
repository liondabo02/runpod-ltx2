from datetime import datetime, timezone

from ahos.acceptance_controller import AcceptanceController
from ahos.production_proof_gate import ProofBundleReport
from ahos.runtime_audit import RuntimeAuditReport
from ahos.verification_baseline import VerificationBaseline


CORE = frozenset({
    "holding_platform",
    "coding_reliability",
    "runtime_health",
    "recovery",
    "owner_gates",
    "evidence",
})

PRODUCTION = frozenset({
    "deployment_proof",
    "autonomous_runtime_proof",
    "recovery_proof",
    "studio_acceptance",
    "identity_acceptance",
    "language_acceptance",
})


def _baseline(commit="abc", platform="windows"):
    return VerificationBaseline(
        verified_at=datetime(2026, 10, 18, tzinfo=timezone.utc),
        commit_sha=commit,
        platform=platform,
        proofs=CORE,
    )


def _production(*, commit="abc", platform="windows", proofs=PRODUCTION, ready=True):
    return ProofBundleReport(
        ready=ready,
        proven=proofs,
        blockers=() if ready else ("studio_acceptance:missing",),
        commit_sha=commit,
        platform=platform,
    )


def _runtime(healthy=True):
    return RuntimeAuditReport(
        healthy=healthy,
        heartbeat_age_seconds=1.0,
        service_state="idle",
        coding_counts={},
        department_counts={},
        blockers=() if healthy else ("stale_heartbeat",),
    )


def test_acceptance_controller_reaches_proven_readiness_only_with_all_evidence():
    report = AcceptanceController().evaluate(
        core_baseline=_baseline(),
        production_proofs=_production(),
        runtime=_runtime(),
    )
    assert report.ready is True
    assert report.score == 100.0
    assert report.requirements.platform_ready is True
    assert report.requirements.department_acceptance_ready is True


def test_acceptance_controller_fails_on_commit_mismatch():
    report = AcceptanceController().evaluate(
        core_baseline=_baseline(commit="a"),
        production_proofs=_production(commit="b"),
        runtime=_runtime(),
    )
    assert report.ready is False
    assert "evidence_commit_mismatch" in report.blockers


def test_acceptance_controller_fails_if_department_proof_missing():
    proofs = PRODUCTION - {"identity_acceptance"}
    report = AcceptanceController().evaluate(
        core_baseline=_baseline(),
        production_proofs=_production(proofs=proofs, ready=False),
        runtime=_runtime(),
    )
    assert report.ready is False
    assert report.requirements.department_acceptance_ready is False
    assert report.score < 99.0


def test_acceptance_controller_fails_closed_on_unhealthy_runtime():
    report = AcceptanceController().evaluate(
        core_baseline=_baseline(),
        production_proofs=_production(),
        runtime=_runtime(healthy=False),
    )
    assert report.ready is False
    assert any(item.startswith("runtime:") for item in report.blockers)
