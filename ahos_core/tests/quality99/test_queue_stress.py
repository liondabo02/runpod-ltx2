from ahos_quality99.queue_stress import run_synthetic_queue_stress


def test_100_synthetic_tasks_have_no_duplicate_or_loss():
    report = run_synthetic_queue_stress(task_count=100)
    assert report.passed is True
    assert report.requested == 100
    assert report.unique_records == 100
    assert report.duplicate_records == 0
    assert report.claimed == 100
    assert report.terminal == 100
    assert report.lost == 0
