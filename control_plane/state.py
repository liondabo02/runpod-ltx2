from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    agent TEXT NOT NULL,
    kind TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(run_id) REFERENCES runs(id)
);
"""


class StateStore:
    def __init__(self, path: str | Path = ".miniverse/control_plane.db") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as con:
            con.executescript(SCHEMA)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        con = sqlite3.connect(self.path)
        try:
            yield con
            con.commit()
        finally:
            con.close()

    def create_run(self, task: str) -> int:
        with self.connect() as con:
            cur = con.execute("INSERT INTO runs(task, status) VALUES (?, ?)", (task, "running"))
            return int(cur.lastrowid)

    def add_message(self, run_id: int, agent: str, kind: str, payload: Any) -> None:
        encoded = json.dumps(payload, ensure_ascii=False) if not isinstance(payload, str) else payload
        with self.connect() as con:
            con.execute(
                "INSERT INTO messages(run_id, agent, kind, payload) VALUES (?, ?, ?, ?)",
                (run_id, agent, kind, encoded),
            )

    def finish_run(self, run_id: int, status: str = "completed") -> None:
        with self.connect() as con:
            con.execute("UPDATE runs SET status=? WHERE id=?", (status, run_id))
