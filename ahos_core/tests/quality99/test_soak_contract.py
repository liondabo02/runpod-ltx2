import pytest

from ahos_quality99.soak import run_bounded_soak


def test_small_bounded_soak_contract():
    report = run_bounded_soak(queue_rounds=1, tasks_per_round=10, recovery_rounds=1)
    assert report.passed is True
    assert report.queue_tasks_total == 10


@pytest.mark.parametrize("kwargs", [
    {"queue_rounds": 0},
    {"queue_rounds": 51},
    {"tasks_per_round": 0},
    {"tasks_per_round": 1001},
    {"recovery_rounds": 0},
    {"recovery_rounds": 21},
])
def test_soak_limits_are_bounded(kwargs):
    with pytest.raises(ValueError):
        run_bounded_soak(**kwargs)
