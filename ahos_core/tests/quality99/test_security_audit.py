from ahos_quality99.security_audit import run_security_audit


def test_security_audit_blocks_external_paid_destructive_and_prompt_attacks():
    report = run_security_audit()
    assert report.passed is True
    assert report.owner_gate_enforced is True
    assert report.prompt_attacks_detected is True
    assert report.worker_privilege_blocked is True
