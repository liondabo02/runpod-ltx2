from ahos_quality99.process_recovery_e2e import run_process_recovery_e2e


def test_real_process_boundary_recovers_expired_worker_lease():
    report = run_process_recovery_e2e()
    assert report.passed is True
    assert report.first_process_claimed is True
    assert report.second_process_reclaimed is True
    assert report.attempts_after_recovery == 2
    assert report.lost is False
