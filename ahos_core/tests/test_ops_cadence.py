"""Haftalık ritim: planlama, tekrar koruması (idempotency) ve rapor."""

from __future__ import annotations

import json

from ahos.ops_cadence import DEFAULT_OBJECTIVES, _week_tag, run_cycle, write_report


def test_week_tag_is_stable_within_a_week():
    from datetime import datetime, timezone

    first = _week_tag(datetime(2026, 11, 2, tzinfo=timezone.utc))
    second = _week_tag(datetime(2026, 11, 5, tzinfo=timezone.utc))
    assert first == second
    assert first.startswith("2026W")


def test_cycle_creates_one_mission_per_department(tmp_path):
    results = run_cycle(tmp_path, departments=["finance", "marketing"], week="2026W45")

    assert [item.department for item in results] == ["finance", "marketing"]
    assert all(item.mission_id == f"CAD-{item.department}-2026W45" for item in results)
    assert all(item.status in {"completed", "failed", "atlandı"} for item in results)

    report = write_report(tmp_path, results, tag="2026W45")
    assert report.is_file()
    body = report.read_text(encoding="utf-8")
    assert "Haftalık ritim raporu" in body
    assert "finance" in body and "marketing" in body


def test_second_run_in_the_same_week_does_not_duplicate(tmp_path):
    run_cycle(tmp_path, departments=["data"], week="2026W46")
    second = run_cycle(tmp_path, departments=["data"], week="2026W46")

    assert len(second) == 1
    assert "zaten açıldı" in second[0].reason

    from ahos.autonomous_company import PersistentMissionQueue

    queue = PersistentMissionQueue(tmp_path / "company-service.db")
    stored = queue.get("CAD-data-2026W46")
    assert stored is not None


def test_dry_run_writes_nothing(tmp_path):
    results = run_cycle(tmp_path, departments=["sales"], week="2026W47", dry_run=True)
    assert results[0].status == "planlandı"
    assert not (tmp_path / "reports").exists()
    assert not (tmp_path / "company-service.db").exists()


def test_every_department_has_a_weekly_objective(tmp_path):
    assert len(set(DEFAULT_OBJECTIVES.values())) == len(DEFAULT_OBJECTIVES)
    for department, objective in DEFAULT_OBJECTIVES.items():
        assert department.islower() or "-" in department
        assert len(objective) > 15, department
