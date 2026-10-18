from ahos_quality99.monitoring_rehearsal import run_monitoring_rehearsal


def test_monitoring_detects_stale_heartbeat_and_error_budget_breach():
    report = run_monitoring_rehearsal()
    assert report.passed is True
