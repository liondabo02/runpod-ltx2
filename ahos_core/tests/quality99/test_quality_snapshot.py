from ahos_quality99.quality_snapshot import current_snapshot


def test_snapshot_never_claims_99_while_real_blockers_are_open():
    snapshot = current_snapshot()
    assert snapshot.score == 86.67
    assert snapshot.target_reached is False
    assert "windows_coding_queue_lock_race" in snapshot.blockers
    assert "real_product_acceptance" in snapshot.blockers
    assert "android_device_e2e" in snapshot.blockers
    assert "performance_metrics_not_integrated_into_assignment" in snapshot.blockers
