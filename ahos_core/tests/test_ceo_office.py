from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ahos.ceo_office import daily_brief, decide, review, set_goal


def _runtime(tmp_path: Path) -> Path:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    con = sqlite3.connect(runtime / "company-service.db")
    con.execute(
        "create table missions (mission_id text primary key, objective text, "
        "primary_department text, status text, attempts integer, max_attempts integer, "
        "next_attempt_at text, lease_owner text, lease_until text, created_at text, "
        "updated_at text, last_error text, result_json text)"
    )
    con.executemany(
        "insert into missions (mission_id, objective, primary_department, status, last_error, updated_at) "
        "values (?,?,?,?,?,datetime('now'))",
        [
            ("CMD-oyun-a", "x", "oyun", "completed", None),
            ("CMD-oyun-b", "x", "oyun", "completed", None),
            ("CMD-oyun-c", "x", "oyun", "blocked", "worker execution failed"),
            ("CMD-data-d", "x", "data", "pending", None),
        ],
    )
    con.commit()
    con.close()
    (runtime / "worker-metrics.jsonl").write_text(
        "\n".join(
            json.dumps({"worker_id": worker, "success": ok})
            for worker, ok in [("oyun-manager", True)] * 12 + [("data-analyst", False)] * 12
        )
        + "\n",
        encoding="utf-8",
    )
    return runtime


def test_daily_brief_reports_real_numbers(tmp_path) -> None:
    runtime = _runtime(tmp_path)

    brief = daily_brief(runtime)

    assert brief.completed == 2
    assert brief.blocked == 1
    assert brief.pending == 1
    assert 0 < brief.delivery_rate < 1
    assert (runtime / "ceo" / "last-brief.json").exists()


def test_daily_brief_finds_weakest_worker(tmp_path) -> None:
    runtime = _runtime(tmp_path)

    brief = daily_brief(runtime)

    assert "data-analyst" in brief.weakest_department


def test_set_goal_creates_missions_and_record(tmp_path) -> None:
    runtime = _runtime(tmp_path)

    record = set_goal(runtime, "oyun kalitesini artır", ("oyun", "data"))

    assert record["goal_id"].startswith("GOAL-")
    assert len(record["missions"]) == 2
    goals = (runtime / "ceo" / "goals.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(goals) == 1


def test_review_writes_decision(tmp_path) -> None:
    runtime = _runtime(tmp_path)

    decision = review(runtime, open_task=False)

    assert decision["type"] == "review"
    lines = (runtime / "ceo" / "decisions.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1


def test_decide_answers_weakness_question(tmp_path) -> None:
    runtime = _runtime(tmp_path)

    record = decide(runtime, "en zayıf halka neresi")

    assert record["action"] == "review"
    assert "zayıf" in record["answer"].casefold()


def test_decide_answers_blocker_question(tmp_path) -> None:
    runtime = _runtime(tmp_path)

    record = decide(runtime, "engeller neler")

    assert record["action"] == "retry-blocked"
