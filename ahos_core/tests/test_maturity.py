from ahos.maturity import (
    CapabilityEvidence,
    CapabilityState,
    evaluate_maturity,
)


def test_maturity_cannot_claim_99_without_runtime_proof():
    report = evaluate_maturity([
        CapabilityEvidence("deployment_proof", 1, CapabilityState.IMPLEMENTED),
        CapabilityEvidence("autonomous_runtime_proof", 1, CapabilityState.IMPLEMENTED),
        CapabilityEvidence("recovery_proof", 1, CapabilityState.IMPLEMENTED),
        CapabilityEvidence("control_plane", 97, CapabilityState.PROVEN),
    ])
    assert report.raw_score > 99
    assert report.score == 95.0
    assert set(report.blockers) == {
        "deployment_proof",
        "autonomous_runtime_proof",
        "recovery_proof",
    }


def test_maturity_reaches_99_only_when_critical_proof_gates_are_proven():
    report = evaluate_maturity([
        CapabilityEvidence("deployment_proof", 1, CapabilityState.PROVEN, "runner receipt"),
        CapabilityEvidence("autonomous_runtime_proof", 1, CapabilityState.PROVEN, "24h receipt"),
        CapabilityEvidence("recovery_proof", 1, CapabilityState.PROVEN, "restart drill"),
        CapabilityEvidence("control_plane", 97, CapabilityState.PROVEN, "CI"),
    ])
    assert report.score == 100.0
    assert report.blockers == ()
