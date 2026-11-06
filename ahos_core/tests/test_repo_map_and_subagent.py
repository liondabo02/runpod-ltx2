from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ahos import subagent
from ahos.repo_map import rank, repo_map_text, scan


def test_scan_and_symbols(tmp_path) -> None:
    (tmp_path / "a.py").write_text("def hello():\n    pass\nclass Foo:\n    pass\n", encoding="utf-8")
    (tmp_path / "b.js").write_text("function bar() {}\nconst baz = 1;\n", encoding="utf-8")

    maps = scan(tmp_path)
    paths = {m.path for m in maps}

    assert {"a.py", "b.js"} <= paths
    assert any("hello" in symbol for m in maps for symbol in m.symbols)


def test_scan_ignores_android(tmp_path) -> None:
    (tmp_path / "android").mkdir()
    (tmp_path / "android" / "x.js").write_text("function hidden() {}\n", encoding="utf-8")

    maps = scan(tmp_path)

    assert all("android" not in m.path for m in maps)


def test_rank_prefers_task_match(tmp_path) -> None:
    (tmp_path / "card-keys.js").write_text("function cards() {}\n", encoding="utf-8")
    (tmp_path / "other.js").write_text("function unrelated() {}\n", encoding="utf-8")
    maps = scan(tmp_path)

    ranked = rank(maps, "card-keys.js dosyasına yorum ekle")

    assert ranked[0].path == "card-keys.js"


def test_repo_map_text_contains_header(tmp_path) -> None:
    (tmp_path / "a.py").write_text("def x():\n    pass\n", encoding="utf-8")

    text = repo_map_text(tmp_path, "x fonksiyonunu düzelt")

    assert text.startswith("### Depo haritası")
    assert "a.py" in text


def test_subagent_returns_summary_and_writes_record(tmp_path) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    con = sqlite3.connect(runtime / "company-service.db")
    con.execute("create table missions (mission_id text, status text)")
    con.execute("insert into missions values ('m1','completed')")
    con.commit()
    con.close()

    result = subagent.run(runtime, "oyun kalitesini incele")

    assert result.run_id.startswith("SUB-")
    assert "Kuyruk" in result.summary
    assert (runtime / "subagents" / f"{result.run_id}.json").exists()


def test_subagent_includes_repo_context(tmp_path) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    project = tmp_path / "project"
    project.mkdir()
    (project / "game.js").write_text("function game() {}\n", encoding="utf-8")

    result = subagent.run(runtime, "game.js dosyasını incele", project_root=project)

    assert "game.js" in result.summary


def test_subagent_record_is_json(tmp_path) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()

    result = subagent.run(runtime, "deneme")
    payload = json.loads((runtime / "subagents" / f"{result.run_id}.json").read_text(encoding="utf-8"))

    assert payload["task"] == "deneme"
    assert payload["run_id"] == result.run_id
