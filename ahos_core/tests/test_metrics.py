from __future__ import annotations

import pytest

from ahos import MissionMetric, MissionStatus, MetricsSnapshot, report_metrics


def test_snapshot_aggregates_counts_rates_latency_and_cost() -> None:
    snapshot = MetricsSnapshot.from_missions(
        [
            MissionMetric(MissionStatus.COMPLETED, latency_seconds=2.0, estimated_cost_usd=0.02),
            MissionMetric(MissionStatus.FAILED, latency_seconds=4.0, estimated_cost_usd=0.03),
            MissionMetric(MissionStatus.PENDING, latency_seconds=1.0),
        ]
    )

    assert snapshot.total_missions == 3
    assert snapshot.successful_missions == 1
    assert snapshot.failed_missions == 1
    assert snapshot.success_rate == pytest.approx(1 / 3)
    assert snapshot.failure_rate == pytest.approx(1 / 3)
    assert snapshot.average_latency_seconds == pytest.approx(7 / 3)
    assert snapshot.estimated_cost_usd == pytest.approx(0.05)


def test_empty_snapshot_has_zero_rates_and_report_is_serializable() -> None:
    snapshot = MetricsSnapshot.from_missions([])

    assert snapshot.success_rate == 0.0
    assert snapshot.failure_rate == 0.0
    assert report_metrics(snapshot) == {
        "total_missions": 0,
        "successful_missions": 0,
        "failed_missions": 0,
        "success_rate": 0.0,
        "failure_rate": 0.0,
        "average_latency_seconds": 0.0,
        "estimated_cost_usd": 0.0,
    }


def test_metrics_reject_negative_or_inconsistent_values() -> None:
    with pytest.raises(ValueError):
        MissionMetric(MissionStatus.COMPLETED, latency_seconds=-1.0)
    with pytest.raises(ValueError):
        MetricsSnapshot(1, 1, 1, 0.0, 0.0)
    with pytest.raises(ValueError):
        MetricsSnapshot(0, 0, 0, 0.0, float("inf"))
