from ahos_quality99.company_service_soak import run_company_service_soak


def test_real_company_service_survives_bounded_unattended_soak():
    report = run_company_service_soak(duration_seconds=10.0)
    assert report.passed is True
    assert report.clean_stop is True
    assert report.error_states == 0
    assert report.unique_timestamps >= 10
    assert report.max_gap_seconds <= 1.0
