"""Failure analytics: taxonomy, rates and self-improvement backlog."""

from __future__ import annotations

import json

from ahos.failure_analytics import analyse, improvement_tasks, write_backlog


def _runtime(tmp_path, missions, errors=()):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    with (runtime / "daemon-missions.jsonl").open("w", encoding="utf-8") as handle:
        for row in missions:
            handle.write(json.dumps(row) + "\n")
    with (runtime / "errors.jsonl").open("w", encoding="utf-8") as handle:
        for row in errors:
            handle.write(json.dumps(row) + "\n")
    return runtime


def test_rates_and_causes(tmp_path) -> None:
    runtime = _runtime(
        tmp_path,
        [
            {"status": "routed", "changed_files": 2},
            {"status": "routed", "changed_files": 1},
            {"status": "routed", "changed_files": 0},
            {"status": "blocked", "changed_files": 1},
        ],
        [{"message": "model çağrısı başarısız: HTTP 429"}],
    )

    report = analyse(runtime)

    assert report["missions"] == 4
    assert report["delivered"] == 2
    assert report["delivery_rate"] == 0.5
    assert report["error_rate"] == 0.5
    assert report["causes"]["no_delivery"] == 1
    assert report["causes"]["acceptance_failed"] == 1
    assert report["causes"]["model_unavailable"] == 1


def test_improvement_backlog_is_deduplicated(tmp_path) -> None:
    runtime = _runtime(
        tmp_path,
        [{"status": "routed", "changed_files": 0} for _ in range(3)],
    )
    report = analyse(runtime)

    tasks = improvement_tasks(report)
    path = write_backlog(runtime, tasks)
    write_backlog(runtime, tasks)

    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == len(tasks), "aynı iyileştirme görevi tekrar yazılmamalı"


def test_below_threshold_creates_no_task(tmp_path) -> None:
    runtime = _runtime(tmp_path, [{"status": "routed", "changed_files": 0}])

    tasks = improvement_tasks(analyse(runtime))

    assert tasks == []
