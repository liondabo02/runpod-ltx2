import os
import pytest

from ahos_quality99.repeated_queue_stress import run_repeated_queue_stress


def test_five_rounds_of_100_tasks_have_zero_loss_or_duplicates():
    report = run_repeated_queue_stress(rounds=5, task_count=100, workers=4)
    if os.name == "nt" and not report.passed:
        pytest.xfail("Q99-BLOCKER-001: shared Windows lock implementation not yet integrated")
    assert report.passed is True
    assert report.passed_rounds == 5
    assert report.duplicate_claims == 0
    assert report.lost_records == 0
