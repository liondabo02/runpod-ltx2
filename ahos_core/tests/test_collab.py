from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ahos import collab


def _runtime(tmp_path: Path) -> Path:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    con = sqlite3.connect(runtime / "company-service.db")
    con.execute(
        "create table missions (mission_id text primary key, objective text, primary_department text, "
        "status text, attempts integer, max_attempts integer, next_attempt_at text, "
        "lease_owner text, lease_until text, created_at text, updated_at text, "
        "last_error text, result_json text)"
    )
    con.commit()
    con.close()
    return runtime


def test_split_uses_multiple_departments() -> None:
    parts = collab.split("oyun için video hazırla ve test et")

    departments = {part.department for part in parts}

    assert "oyun" in departments
    assert len(parts) >= 2


def test_split_falls_back_to_genel() -> None:
    parts = collab.split("alakasız bir istek")

    assert parts[0].department == "genel"


def test_split_limits_departments() -> None:
    parts = collab.split("oyun kod video test rapor hukuk pazarlama bütçe", limit=2)

    assert len(parts) == 2


def test_launch_creates_missions_and_record(tmp_path) -> None:
    runtime = _runtime(tmp_path)

    collaboration = collab.launch(runtime, "oyun için video ve test hazırla")

    assert collaboration.ticket.startswith("COL-")
    assert collaboration.missions
    record = (runtime / "collaborations.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(record) == 1


def test_status_reports_progress(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    collaboration = collab.launch(runtime, "oyun ve software işi")

    con = sqlite3.connect(runtime / "company-service.db")
    # Tamamlanma ancak tutarli bir result_json ile yazilabilir (DB korumasi).
    result = json.dumps({"status": "completed", "steps": []})
    for mission in collaboration.missions:
        con.execute(
            "insert or replace into missions "
            "(mission_id, objective, primary_department, status, result_json) "
            "values (?,?,?,?,?)",
            (mission, "x", "oyun", "completed", result),
        )
    con.commit()
    con.close()

    payload = collab.status(runtime, collaboration.ticket)

    assert payload["found"] is True
    assert payload["completed"] == payload["total"]
    assert payload["progress"] == 1.0


def test_status_unknown_ticket(tmp_path) -> None:
    runtime = _runtime(tmp_path)

    payload = collab.status(runtime, "COL-YOK")

    assert payload["found"] is False
