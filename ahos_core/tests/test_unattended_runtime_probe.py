from datetime import datetime, timedelta, timezone

from ahos.unattended_runtime_probe import UnattendedRuntimeProbe


def _rows(count=6, step=10, state="idle"):
    start = datetime(2026, 10, 18, tzinfo=timezone.utc)
    return [
        {"timestamp": (start + timedelta(seconds=i * step)).isoformat(), "state": state}
        for i in range(count)
    ]


def test_unattended_runtime_probe_passes_contiguous_window():
    report = UnattendedRuntimeProbe(
        minimum_observed_seconds=40,
        maximum_heartbeat_gap_seconds=15,
        minimum_samples=5,
    ).evaluate(_rows())
    assert report.passed is True
    assert report.observed_seconds == 50


def test_unattended_runtime_probe_rejects_short_window():
    report = UnattendedRuntimeProbe(
        minimum_observed_seconds=100,
        maximum_heartbeat_gap_seconds=15,
        minimum_samples=5,
    ).evaluate(_rows())
    assert report.passed is False
    assert "observation_window_too_short" in report.blockers


def test_unattended_runtime_probe_requires_healthy_end():
    rows = _rows()
    rows[-1]["state"] = "error"
    report = UnattendedRuntimeProbe(
        minimum_observed_seconds=40,
        maximum_heartbeat_gap_seconds=15,
        minimum_samples=5,
    ).evaluate(rows)
    assert "runtime_not_healthy_at_end" in report.blockers
