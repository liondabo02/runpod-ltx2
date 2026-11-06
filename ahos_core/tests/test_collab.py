"""Departmanlar arası iş birliği: bölme, devir ve portföy."""

from __future__ import annotations

import json

from ahos.collab import handoff, load_handoffs, portfolio, split


def test_split_names_the_right_departments():
    parts = split("oyun için yeni bir level tasarla ve test et")
    departments = [part.department for part in parts]

    assert "oyun" in departments
    assert "quality" in departments
    assert len(parts) <= 3
    assert all(part.objective for part in parts)


def test_split_falls_back_to_genel():
    parts = split("bilinmeyen konu")
    assert [part.department for part in parts] == ["genel"]


def test_handoff_is_recorded_and_read_back(tmp_path):
    record = handoff(tmp_path, "oyun", "software", "oyun motorunu hazırla",
                     depends_on=["M-1"])
    assert record["status"] == "pending"
    assert record["from"] == "oyun" and record["to"] == "software"

    stored = load_handoffs(tmp_path)
    assert len(stored) == 1
    assert stored[0]["depends_on"] == ["M-1"]
    assert json.loads((tmp_path / "handoffs.jsonl").read_text(encoding="utf-8").strip())["to"] == "software"


def test_portfolio_summarises_departments_and_handoffs(tmp_path):
    handoff(tmp_path, "oyun", "software", "motor")
    report = portfolio(tmp_path)

    assert report["handoffs"]["total"] == 1
    assert report["handoffs"]["pending"] == 1
    assert isinstance(report["departments"], dict)
