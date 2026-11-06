from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from ahos.arge import INTERVAL_SECONDS, measure, tick


def _runtime(tmp_path: Path) -> Path:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (runtime / "knowledge").mkdir()
    return runtime


def _write_metrics(runtime: Path, rows: list[dict]) -> None:
    (runtime / "worker-metrics.jsonl").write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8"
    )


def _write_missions(runtime: Path, rows: list[tuple[str, str, str]]) -> None:
    con = sqlite3.connect(runtime / "company-service.db")
    con.execute(
        "create table missions (mission_id text primary key, objective text, "
        "primary_department text, status text, last_error text, updated_at text)"
    )
    con.executemany(
        "insert into missions (mission_id, objective, primary_department, status, last_error, updated_at) "
        "values (?, ?, ?, ?, ?, datetime('now'))",
        rows,
    )
    con.commit()
    con.close()


def test_measure_computes_rates(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    _write_metrics(
        runtime,
        [
            {"department": "oyun", "success": True},
            {"department": "oyun", "success": False},
            {"department": "data", "success": True},
        ],
    )

    rates, _reasons = measure(runtime)

    assert rates["oyun"] == 0.5
    assert rates["data"] == 1.0


def test_tick_creates_lessons_and_state(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    _write_metrics(
        runtime,
        [
            {"department": "oyun", "success": True},
            {"department": "oyun", "success": False},
            {"department": "oyun", "success": False},
        ],
    )
    _write_missions(
        runtime,
        [
            ("CMD-oyun-a-1", "x", "oyun", "blocked", "QA failed: kabul"),
            ("CMD-oyun-a-2", "y", "oyun", "blocked", "QA failed: kabul"),
        ],
    )

    result = tick(runtime, force=True, now=1000.0)

    assert result.ran is True
    assert "oyun" in result.weakest
    assert (runtime / "arge-state.json").exists()


def test_tick_respects_interval(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    tick(runtime, force=True, now=1000.0)

    second = tick(runtime, now=1000.0 + INTERVAL_SECONDS - 5)

    assert second.ran is False


def test_tick_runs_again_after_interval(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    tick(runtime, force=True, now=1000.0)

    second = tick(runtime, now=1000.0 + INTERVAL_SECONDS + 1)

    assert second.ran is True


def test_state_records_rates(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    _write_metrics(runtime, [{"department": "data", "success": True}])

    tick(runtime, force=True, now=2000.0)

    payload = json.loads((runtime / "arge-state.json").read_text(encoding="utf-8"))
    assert payload["rates"]["data"] == 1.0
    assert payload["last_at"]
