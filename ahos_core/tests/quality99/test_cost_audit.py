from ahos_quality99.cost_audit import run_zero_cost_audit


def test_quality_program_cost_is_hard_zero():
    report = run_zero_cost_audit()
    assert report.passed is True
    assert report.total_allowed_paid_usd == 0.0
