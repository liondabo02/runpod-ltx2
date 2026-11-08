"""Initiative (otonom hedef) testleri — hermetik, tmp_path kullanır."""

from __future__ import annotations

import json
from pathlib import Path

from ahos.initiative import last, tick


def _runtime(tmp_path: Path, *, pending: int = 0, weakest: str = "oyun") -> Path:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "training-report.json").write_text(
        json.dumps(
            {
                "departments": 2,
                "workers": 2,
                "results": [
                    {"department": weakest, "score": 60},
                    {"department": "software", "score": 95},
                ],
            }
        ),
        encoding="utf-8",
    )
    (runtime / "mission-stats.json").write_text(json.dumps({"pending": pending}), encoding="utf-8")
    return runtime


def test_tick_creates_goal_when_pending_less_than_8(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path, pending=3)

    result = tick(runtime, [{"department_id": "oyun"}, {"department_id": "software"}])

    assert result["created"] == 1
    assert result["department"] == "oyun"
    assert (runtime / "initiative.jsonl").exists()


def test_tick_no_goal_when_pending_at_least_8(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path, pending=9)

    result = tick(runtime, [{"department_id": "oyun"}])

    assert result["created"] == 0


def test_tick_appends_line(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path, pending=0)

    tick(runtime, [])
    tick(runtime, [])

    lines = (runtime / "initiative.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2


def test_last_returns_latest(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path, pending=0)
    tick(runtime, [])

    record = last(runtime)

    assert record is not None
    assert record["department"] == "oyun"
    assert record["score"] == 0.8


def test_last_none_when_no_file(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()

    assert last(runtime) is None
