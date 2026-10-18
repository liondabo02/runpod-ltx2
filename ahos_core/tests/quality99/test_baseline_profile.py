from ahos_quality99.baseline_profile import current_baseline, phase2_current


def test_baseline_is_measured_not_claimed_99():
    report = current_baseline()
    assert report.score == 64.0
    assert report.target_reached is False
    assert "recovery" in report.high_risk_open
    assert "data_integrity" in report.high_risk_open
    assert "security" in report.high_risk_open
    assert "real_product" in report.high_risk_open
    assert "concurrency" in report.high_risk_open


def test_phase2_proofs_improve_score_without_claiming_99():
    report = phase2_current()
    assert report.score == 74.67
    assert report.target_reached is False
    assert "concurrency" in report.high_risk_open
    assert "recovery" in report.high_risk_open
    assert "real_product" in report.high_risk_open
