from ahos_quality99.baseline_profile import current_baseline


def test_baseline_is_measured_not_claimed_99():
    report = current_baseline()
    assert report.score == 69.33
    assert report.target_reached is False
    assert "recovery" in report.high_risk_open
    assert "data_integrity" in report.high_risk_open
    assert "security" in report.high_risk_open
    assert "real_product" in report.high_risk_open
