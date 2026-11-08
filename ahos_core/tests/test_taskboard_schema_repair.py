"""Schema migration and blocked-queue safety regression coverage."""
from __future__ import annotations

import importlib.util
import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2] / "tools"


def _tool(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_legacy_empty_board_migration_preserves_backup(tmp_path):
    board = tmp_path / "taskboard.json"
    board.write_text("{}", encoding="utf-8")
    migrate = _tool("repair_taskboard_schema").migrate
    preview = migrate(board)
    assert preview["status"] == "legacy-empty-preview"
    assert board.read_text(encoding="utf-8") == "{}"
    result = migrate(board, apply=True)
    assert result["status"] == "migrated" and result["changed"]
    assert Path(result["backup"]).read_bytes() == b"{}"
    assert json.loads(board.read_text(encoding="utf-8"))["tasks"] == []
    assert migrate(board, apply=True)["status"] == "already-valid"


def test_schema_repair_rejects_nonempty_unknown_board(tmp_path):
    board = tmp_path / "taskboard.json"
    original = '{"active": {"some-task": {"owner": "worker"}}}'
    board.write_text(original, encoding="utf-8")
    result = _tool("repair_taskboard_schema").migrate(board, apply=True)
    assert result["status"] == "unknown-invalid"
    assert board.read_text(encoding="utf-8") == original
    assert not list(tmp_path.glob("*.backup-*"))


def test_unlock_does_not_requeue_on_invalid_board(tmp_path, monkeypatch):
    board = tmp_path / "taskboard.json"
    board.write_text("{}", encoding="utf-8")
    db = sqlite3.connect(tmp_path / "company-service.db")
    db.execute("create table missions (mission_id text, status text, last_error text)")
    db.execute("insert into missions values ('blocked-1','blocked','real QA failure')")
    db.commit()
    db.close()

    unlock = _tool("unlock_blocked")
    monkeypatch.setattr(unlock, "RUNTIME", tmp_path)
    assert unlock.main(40, apply=True) == 2
    with sqlite3.connect(tmp_path / "company-service.db") as c:
        assert c.execute("select status from missions").fetchone()[0] == "blocked"
    assert board.read_text(encoding="utf-8") == "{}"
