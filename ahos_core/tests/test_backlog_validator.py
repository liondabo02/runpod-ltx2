import json
import subprocess
import sys
from pathlib import Path

from ahos.backlog_validator import validate_backlog


AHOS_CORE = Path(__file__).resolve().parents[1]
BACKLOG_PATH = AHOS_CORE / "AHOS_BACKLOG.json"


def backlog_data() -> dict:
    return json.loads(BACKLOG_PATH.read_text(encoding="utf-8-sig"))


def test_loader_accepts_windows_powershell_utf8_bom(tmp_path: Path):
    from ahos.backlog_validator import load_and_validate

    source = tmp_path / "bom-backlog.json"
    source.write_text(json.dumps(valid_backlog_data()), encoding="utf-8-sig")

    assert load_and_validate(source).is_valid is True


def valid_backlog_data() -> dict:
    data = backlog_data()
    for task in data["tasks"]:
        if task["status"] == "completed" and "completed_at" not in task:
            task["completed_at"] = "2026-09-20T00:00:00Z"
    return data


def test_current_backlog_reports_missing_completed_timestamps():
    result = validate_backlog(backlog_data())

    assert result.is_valid is False
    assert result.errors == (
        "tasks[37].completed_at is required for completed tasks",
        "tasks[38].completed_at is required for completed tasks",
        "tasks[39].completed_at is required for completed tasks",
        "tasks[40].completed_at is required for completed tasks",
    )


def test_validator_requires_top_level_sections():
    data = valid_backlog_data()
    data.pop("rules")
    data.pop("tasks")

    result = validate_backlog(data)

    assert result.errors == (
        "missing top-level field: rules",
        "missing top-level field: tasks",
        "top-level rules must be an object",
        "top-level tasks must be an array",
    )


def test_validator_reports_duplicate_ids_and_invalid_values():
    data = valid_backlog_data()
    data["tasks"][1] = dict(data["tasks"][0])
    data["tasks"][1].update(status="unknown", authority="E", risk="critical")

    result = validate_backlog(data)

    assert result.is_valid is False
    assert result.errors == (
        "duplicate task id: AHOS-001",
        "tasks[1].status must be one of ['blocked', 'completed', 'in_progress', 'planned']",
        "tasks[1].authority must be one of ['A', 'B', 'C', 'D']",
        "tasks[1].risk must be one of ['high', 'low', 'medium']",
    )


def test_validator_enforces_governance_and_completion_rules():
    data = valid_backlog_data()
    data["tasks"][0] = dict(
        data["tasks"][0],
        authority="C",
        requires_owner_approval=False,
        completed_at=None,
    )

    result = validate_backlog(data)

    assert result.is_valid is False
    assert result.errors == (
        "tasks[0].requires_owner_approval must be True for authority C",
        "tasks[0].completed_at is required for completed tasks",
    )


def test_validator_requires_the_governance_rules():
    data = valid_backlog_data()
    data["rules"] = {
        "autonomous_authority": ["A", "B", "C"],
        "never_auto_merge_main": False,
        "owner_approval_required": ["D"],
    }

    result = validate_backlog(data)

    assert result.is_valid is False
    assert result.errors == (
        "rules.autonomous_authority must be exactly ['A', 'B']",
        "rules.never_auto_merge_main must be true",
        "rules.owner_approval_required must be exactly ['C', 'D']",
    )


def test_report_command_is_read_only_and_returns_success(tmp_path: Path):
    source = tmp_path / "backlog.json"
    original = BACKLOG_PATH.read_bytes()
    source.write_text(json.dumps(valid_backlog_data()), encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, "-m", "ahos.backlog_validator", str(source)],
        cwd=AHOS_CORE,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert completed.stdout == f"VALID: {source} (45 tasks)\n"
    assert completed.stderr == ""
    assert BACKLOG_PATH.read_bytes() == original


def test_report_command_returns_failure_for_invalid_backlog(tmp_path: Path):
    source = tmp_path / "invalid.json"
    data = valid_backlog_data()
    data["tasks"][0].pop("completed_at")
    source.write_text(json.dumps(data), encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, "-m", "ahos.backlog_validator", str(source)],
        cwd=AHOS_CORE,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 1
    assert completed.stdout == (
        f"INVALID: {source}\n"
        "- tasks[0].completed_at is required for completed tasks\n"
    )
    assert completed.stderr == ""
