from ahos_quality99.worker_performance import WorkerOutcome, WorkerPerformanceModel


def test_worker_performance_ranks_quality_not_just_speed():
    rows = (
        WorkerOutcome("reliable", True, True, 120, 0),
        WorkerOutcome("reliable", True, True, 140, 0),
        WorkerOutcome("fast-bad", True, False, 10, 2),
        WorkerOutcome("fast-bad", False, False, 10, 2),
    )
    ranked = WorkerPerformanceModel().rank(rows)
    assert ranked[0].worker_id == "reliable"
    assert ranked[0].qa_rate == 1.0
