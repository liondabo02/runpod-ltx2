from ahos_quality99.company_service_restart_e2e import run_company_service_restart_e2e


def test_actual_company_service_stops_and_restarts_with_fresh_heartbeat():
    report = run_company_service_restart_e2e()
    assert report.passed is True
    assert report.first_heartbeat_seen is True
    assert report.first_stop_clean is True
    assert report.second_heartbeat_seen is True
    assert report.second_stop_clean is True
    assert report.timestamp_advanced is True
