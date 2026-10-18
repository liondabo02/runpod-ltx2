from ahos.requirement_audit import audit_requirements
from ahos.verification_baseline import VerificationBaseline
from datetime import datetime, timezone


REQS = {
    "HOLDING": "holding",
    "CODING": "coding",
    "RELIABILITY": "reliability",
    "STUDIO": "studio",
    "IDENTITY": "identity",
    "LANGUAGES": "languages",
    "OWNER_GATES": "owner gates",
    "EVIDENCE": "evidence",
}


def _baseline(*proofs):
    return VerificationBaseline(
        verified_at=datetime(2026, 10, 18, tzinfo=timezone.utc),
        commit_sha="abc",
        platform="windows",
        proofs=frozenset(proofs),
    )


def test_platform_can_be_ready_while_department_acceptance_remains_unproven():
    report = audit_requirements(REQS, _baseline(
        "holding_platform", "coding_reliability", "runtime_health",
        "recovery", "owner_gates", "evidence",
    ))
    status = {row["id"]: row["verification"] for row in report.rows}
    assert report.platform_ready is True
    assert report.department_acceptance_ready is False
    assert status["HOLDING"] == "proven"
    assert status["STUDIO"] == "not_proven"


def test_department_acceptance_requires_all_three_proofs():
    report = audit_requirements(REQS, _baseline(
        "studio_acceptance", "identity_acceptance", "language_acceptance",
    ))
    assert report.platform_ready is False
    assert report.department_acceptance_ready is True


def test_missing_baseline_is_not_audited_not_proven():
    report = audit_requirements(REQS, None)
    assert {row["verification"] for row in report.rows} == {"not_audited"}
    assert report.platform_ready is False
    assert report.department_acceptance_ready is False
