"""Daemon döngüsü: bayraklar, durum dosyası, sınırlar."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ahos import daemon


def _runtime_with_db(tmp_path: Path) -> Path:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    con = sqlite3.connect(runtime / "company-service.db")
    con.execute("CREATE TABLE missions (mission_id TEXT, status TEXT, updated_at TEXT)")
    con.executemany(
        "INSERT INTO missions VALUES (?, ?, datetime('now'))",
        [("M-1", "completed"), ("M-2", "completed"), ("M-3", "blocked")],
    )
    con.commit()
    con.close()
    return runtime


def test_mission_counts_reads_the_queue(tmp_path):
    runtime = _runtime_with_db(tmp_path)
    total, last_hour = daemon._mission_counts(runtime)
    assert total == 2
    assert last_hour == 2

    assert daemon._mission_counts(tmp_path / "yok") == (0, 0)


def test_service_state_keeps_existing_fields(tmp_path):
    path = tmp_path / "daemon-state.json"
    path.write_text(json.dumps({"infra": {"x": 1}, "ticks": 5}), encoding="utf-8")

    daemon._write_service_state(tmp_path, ticks=6, status="running")

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["ticks"] == 6
    assert payload["status"] == "running"
    assert payload["infra"] == {"x": 1}


def test_main_runs_one_tick_and_writes_state(tmp_path, monkeypatch):
    runtime = _runtime_with_db(tmp_path)
    calls: list[str] = []

    monkeypatch.setattr(daemon, "tick_once", lambda runtime_dir, departments: calls.append(runtime_dir))

    code = daemon.main(["--once", "--runtime-dir", str(runtime), "--missions-total", "0"])
    assert code in (None, 0)
    assert calls == [str(runtime)]

    state = json.loads((runtime / "daemon-state.json").read_text(encoding="utf-8"))
    assert state["ticks"] == 1
    assert state["status"] == "stopped"
    assert state["last_reason"] == "tek tur tamamlandı"
    assert state["scheduler"]["hour_key"]
    assert not (runtime / "daemon.pid").exists()


def test_main_stops_on_stop_file(tmp_path, monkeypatch):
    runtime = _runtime_with_db(tmp_path)
    (runtime / "daemon.stop").write_text("", encoding="utf-8")
    calls: list[str] = []
    monkeypatch.setattr(daemon, "tick_once", lambda runtime_dir, departments: calls.append(runtime_dir))

    daemon.main(["--runtime-dir", str(runtime), "--missions-total", "0"])

    assert calls == []                      # durdurma dosyası varken hiç tur çalışmaz
    state = json.loads((runtime / "daemon-state.json").read_text(encoding="utf-8"))
    assert state["status"] == "stopped"
    assert "durdurma" in state["last_reason"]
