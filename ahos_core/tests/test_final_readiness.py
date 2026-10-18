from ahos.final_readiness import FinalReadinessEvaluator
from ahos.maturity import MaturityReport
from ahos.requirement_audit import RequirementAudit
from ahos.runtime_audit import RuntimeAuditReport


def _requirements(*, platform: bool = True, departments: bool = True) -> RequirementAudit:
    return RequirementAudit(
        rows=(),
        platform_ready=platform,
        department_acceptance_ready=departments,
    )


def _maturity(*, score: float = 99.0, blockers: tuple[str, ...] = ()) -> MaturityReport:
    return MaturityReport(
        score=score,
        raw_score=score,
        blockers=blockers,
        capabilities=(),
    )


def _runtime(*, healthy: bool = True, blockers: tuple[str, ...] = ()) -> RuntimeAuditReport:
    return RuntimeAuditReport(
        healthy=healthy,
        heartbeat_age_seconds=1.0,
        service_state="running",
        coding_counts={},
        department_counts={},
        blockers=blockers,
    )


def test_final_gate_passes_only_with_all_proofs():
    report = FinalReadinessEvaluator().evaluate(
        requirements=_requirements(),
        maturity=_maturity(),
        runtime=_runtime(),
    )
    assert report.ready is True
    assert report.effective_score == 99.0
    assert report.blockers == ()


def test_department_acceptance_caps_claim_below_99():
    report = FinalReadinessEvaluator().evaluate(
        requirements=_requirements(departments=False),
        maturity=_maturity(score=100.0),
        runtime=_runtime(),
    )
    assert report.ready is False
    assert report.effective_score == 96.0
    assert "department_acceptance_not_proven" in report.blockers


def test_runtime_and_maturity_proofs_fail_closed():
    report = FinalReadinessEvaluator().evaluate(
        requirements=_requirements(),
        maturity=_maturity(
            score=95.0,
            blockers=("deployment_proof", "recovery_proof"),
        ),
        runtime=_runtime(healthy=False, blockers=("stale_heartbeat",)),
    )
    assert report.ready is False
    assert report.effective_score == 95.0
    assert "runtime:stale_heartbeat" in report.blockers
    assert "maturity:deployment_proof" in report.blockers
    assert "maturity:recovery_proof" in report.blockers
    assert any(item.startswith("maturity_score_below_target:") for item in report.blockers)
