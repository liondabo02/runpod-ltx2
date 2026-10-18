from ahos_quality99.dashboard_consistency import DashboardConsistencyAuditor


def test_dashboard_consistency_detects_mismatch():
    report = DashboardConsistencyAuditor().evaluate(
        queue_status={"counts":{"queued":1},"tasks":[{"task_id":"A"}]},
        dashboard_coding={"counts":{"queued":0},"tasks":[]},
    )
    assert report.consistent is False
    assert "count_mismatch:queued" in report.blockers


def test_dashboard_consistency_accepts_equal_read_models():
    payload={"counts":{"queued":1,"running":0},"tasks":[{"task_id":"A"}]}
    report = DashboardConsistencyAuditor().evaluate(
        queue_status=payload,
        dashboard_coding=payload,
    )
    assert report.consistent is True
