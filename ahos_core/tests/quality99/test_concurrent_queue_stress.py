from ahos_quality99.concurrent_queue_stress import run_concurrent_queue_stress


def test_100_tasks_four_synthetic_workers_have_zero_duplicate_claims():
    report = run_concurrent_queue_stress(task_count=100, workers=4)
    assert report.passed is True
    assert report.claimed == 100
    assert report.unique_claims == 100
    assert report.duplicates == 0
    assert report.lost == 0
