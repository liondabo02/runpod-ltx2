"""Pano: kuyruk, maliyet, departman ve ritim özeti."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ahos.dashboard import collect, render_html, render_markdown, write_panel


def _runtime(tmp_path: Path) -> Path:
    runtime = tmp_path / "runtime"
    (runtime / "artifacts").mkdir(parents=True)
    (runtime / "reports").mkdir(parents=True)

    workspace = tmp_path / "workspace"
    (workspace / "tools").mkdir(parents=True)
    gate = workspace / "tools" / "check_offline.py"
    gate.write_text("print('ok')\n", encoding="utf-8")

    (runtime / "departments.json").write_text(json.dumps({
        "departments": [
            {"department_id": "finance", "name": "Finans", "workers": [{"worker_id": "a"}],
             "capabilities": ["budget", "reporting"]},
            {"department_id": "data", "name": "Veri", "workers": [], "capabilities": []},
        ]
    }), encoding="utf-8")
    (runtime / "projects.json").write_text(json.dumps({"projects": [
        {"project_id": "finance-workspace", "department_id": "finance", "path": str(workspace),
         "kind": "document-workspace"},
    ]}), encoding="utf-8")
    (runtime / "artifacts" / "acceptance-baseline.json").write_text(
        json.dumps({str(gate.resolve()).lower(): {"sha256": "x"}}), encoding="utf-8"
    )

    db = sqlite3.connect(runtime / "company-service.db")
    db.execute("CREATE TABLE missions (mission_id TEXT, status TEXT, updated_at TEXT)")
    db.executemany("INSERT INTO missions VALUES (?, ?, ?)", [
        ("M-1", "completed", "2026-11-01T10:00:00"),
        ("M-2", "completed", "2026-11-01T10:05:00"),
        ("M-3", "blocked", "2026-11-01T10:10:00"),
    ])
    db.commit()
    db.close()

    (runtime / "model-spend.jsonl").write_text(
        '{"usd": 0.0, "mission": "M-1"}\n{"usd": 0.5, "mission": "M-2"}\n', encoding="utf-8"
    )
    (runtime / "reports" / "cadence-2026W44-1.md").write_text(
        "# rapor\n\nSonuç: **15/16** departman teslim etti\n", encoding="utf-8"
    )
    return runtime


def test_collect_reads_queue_spend_and_departments(tmp_path):
    snapshot = collect(_runtime(tmp_path))

    assert snapshot["queue"]["total"] == 3
    assert snapshot["queue"]["by_status"]["completed"] == 2
    assert snapshot["spend"]["usd"] == 0.5
    assert snapshot["spend"]["calls"] == 2
    assert [d["department"] for d in snapshot["departments"]] == ["finance", "data"]
    assert snapshot["departments"][0]["gate"] is True
    assert snapshot["departments"][1]["gate"] is False
    assert snapshot["cadence"][0]["completed"] == 15


def test_markdown_and_html_contain_the_numbers(tmp_path):
    snapshot = collect(_runtime(tmp_path))
    markdown = render_markdown(snapshot)
    page = render_html(snapshot)

    assert "toplam görev: **3**" in markdown
    assert "1/2" in markdown
    assert "0.5 $" in markdown
    assert "15/16" in markdown
    assert "<table>" in page and "Finans" in page


def test_write_panel_creates_both_files(tmp_path):
    result = write_panel(_runtime(tmp_path))

    assert Path(result["markdown"]).is_file()
    assert Path(result["html"]).is_file()
    assert result["ready"] == 1
    assert result["departments"] == 2
    assert result["spend_usd"] == 0.5
