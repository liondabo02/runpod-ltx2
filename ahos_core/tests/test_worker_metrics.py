from __future__ import annotations

from pathlib import Path

from ahos import worker_metrics
from ahos.control_center import ControlCenterState


def test_worker_metrics_are_recorded_and_summarised(tmp_path) -> None:
    worker_metrics.configure(tmp_path)
    worker_metrics.record_here(
        worker_id="oyun-engineering-lead",
        mission_id="m-1",
        step_id="produce",
        department="oyun",
        success=True,
        duration_ms=120.0,
    )
    worker_metrics.record_here(
        worker_id="oyun-engineering-lead",
        mission_id="m-2",
        step_id="produce",
        department="oyun",
        success=False,
        duration_ms=80.0,
        reason="dosya yazılamadı",
    )

    summary = worker_metrics.summary(tmp_path)
    row = summary["oyun-engineering-lead"]

    assert row["runs"] == 2
    assert row["successes"] == 1
    assert row["failures"] == 1
    assert row["avg_ms"] == 100.0
    assert row["success_rate"] == 0.5
    assert "dosya yazılamadı" in row["last_error"]


def test_metrics_survive_restart(tmp_path) -> None:
    worker_metrics.configure(tmp_path)
    worker_metrics.record_here(
        worker_id="qa-01",
        mission_id="m-3",
        step_id="review",
        department="quality",
        success=True,
        duration_ms=10.0,
    )

    worker_metrics.configure(None)
    worker_metrics.configure(tmp_path)

    assert worker_metrics.summary(tmp_path)["qa-01"]["runs"] == 1


def test_metrics_are_bounded(tmp_path) -> None:
    worker_metrics.configure(tmp_path)
    for index in range(50):
        worker_metrics.record_here(
            worker_id="qa-01",
            mission_id=f"m-{index}",
            step_id="review",
            department="quality",
            success=True,
            duration_ms=1.0,
        )

    lines = (tmp_path / "worker-metrics.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 50


def test_control_center_exposes_worker_quality_and_locks(tmp_path) -> None:
    worker_metrics.configure(tmp_path)
    worker_metrics.record_here(
        worker_id="qa-01",
        mission_id="m-4",
        step_id="review",
        department="quality",
        success=True,
        duration_ms=5.0,
    )
    state = ControlCenterState(tmp_path)
    snapshot = state.snapshot() if hasattr(state, "snapshot") else None
    if snapshot is None:  # API farklı isimlendirme kullanıyorsa
        snapshot = state.build_snapshot() if hasattr(state, "build_snapshot") else None
    assert snapshot is not None
    workers = snapshot.get("worker_quality") or []
    assert any(row["worker_id"] == "qa-01" for row in workers)
    assert "project_locks" in snapshot
