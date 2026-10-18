from ahos_quality99.recovery_fault_matrix import run_recovery_fault_matrix


def test_recovery_fault_matrix_recovers_expired_lease():
    report = run_recovery_fault_matrix()
    assert report.passed is True
    assert report.lease_expiry_recovered is True
    assert report.idempotent_replay_safe is True
    assert report.lost_tasks == 0
