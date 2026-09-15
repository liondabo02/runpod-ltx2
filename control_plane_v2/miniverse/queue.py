from __future__ import annotations

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TaskRecord:
    id: str
    kind: str
    payload: dict[str, Any]
    status: str
    attempts: int
    max_attempts: int
    available_at: float
    lease_owner: str | None
    lease_expires_at: float | None
    last_error: str | None
    result: dict[str, Any] | None


class SQLiteTaskQueue:
    """Durable task queue with leases, retry scheduling, and crash recovery."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(Path(db_path))
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('pending','running','completed','failed')),
                    attempts INTEGER NOT NULL DEFAULT 0,
                    max_attempts INTEGER NOT NULL DEFAULT 3,
                    available_at REAL NOT NULL,
                    lease_owner TEXT,
                    lease_expires_at REAL,
                    last_error TEXT,
                    result_json TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_tasks_claim ON tasks(status, available_at, lease_expires_at, created_at)"
            )

    def enqueue(
        self,
        kind: str,
        payload: dict[str, Any],
        *,
        max_attempts: int = 3,
        available_at: float | None = None,
        task_id: str | None = None,
    ) -> str:
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        now = time.time()
        task_id = task_id or str(uuid.uuid4())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO tasks(
                    id, kind, payload_json, status, attempts, max_attempts,
                    available_at, created_at, updated_at
                ) VALUES (?, ?, ?, 'pending', 0, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    kind,
                    json.dumps(payload, sort_keys=True),
                    max_attempts,
                    now if available_at is None else available_at,
                    now,
                    now,
                ),
            )
        return task_id

    def claim(self, owner: str, *, lease_seconds: float = 120.0) -> TaskRecord | None:
        if not owner:
            raise ValueError("owner is required")
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be > 0")
        now = time.time()
        lease_expires = now + lease_seconds
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """
                SELECT * FROM tasks
                WHERE attempts < max_attempts
                  AND available_at <= ?
                  AND (
                    status = 'pending'
                    OR (status = 'running' AND lease_expires_at IS NOT NULL AND lease_expires_at <= ?)
                  )
                ORDER BY created_at ASC
                LIMIT 1
                """,
                (now, now),
            ).fetchone()
            if row is None:
                conn.execute("COMMIT")
                return None
            updated = conn.execute(
                """
                UPDATE tasks
                SET status='running', attempts=attempts+1, lease_owner=?, lease_expires_at=?, updated_at=?
                WHERE id=?
                """,
                (owner, lease_expires, now, row["id"]),
            )
            if updated.rowcount != 1:
                conn.execute("ROLLBACK")
                return None
            claimed = conn.execute("SELECT * FROM tasks WHERE id=?", (row["id"],)).fetchone()
            conn.execute("COMMIT")
        return self._row_to_record(claimed)

    def heartbeat(self, task_id: str, owner: str, *, lease_seconds: float = 120.0) -> bool:
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be > 0")
        now = time.time()
        with self._connect() as conn:
            result = conn.execute(
                """
                UPDATE tasks
                SET lease_expires_at=?, updated_at=?
                WHERE id=? AND status='running' AND lease_owner=?
                """,
                (now + lease_seconds, now, task_id, owner),
            )
        return result.rowcount == 1

    def complete(self, task_id: str, owner: str, result: dict[str, Any]) -> bool:
        now = time.time()
        with self._connect() as conn:
            updated = conn.execute(
                """
                UPDATE tasks
                SET status='completed', result_json=?, lease_owner=NULL, lease_expires_at=NULL,
                    last_error=NULL, updated_at=?
                WHERE id=? AND status='running' AND lease_owner=?
                """,
                (json.dumps(result, sort_keys=True), now, task_id, owner),
            )
        return updated.rowcount == 1

    def fail(
        self,
        task_id: str,
        owner: str,
        error: str,
        *,
        retry_delay_seconds: float = 0.0,
    ) -> bool:
        if retry_delay_seconds < 0:
            raise ValueError("retry_delay_seconds must be >= 0")
        now = time.time()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT attempts, max_attempts FROM tasks WHERE id=? AND status='running' AND lease_owner=?",
                (task_id, owner),
            ).fetchone()
            if row is None:
                conn.execute("ROLLBACK")
                return False
            terminal = row["attempts"] >= row["max_attempts"]
            conn.execute(
                """
                UPDATE tasks
                SET status=?, available_at=?, lease_owner=NULL, lease_expires_at=NULL,
                    last_error=?, updated_at=?
                WHERE id=?
                """,
                (
                    "failed" if terminal else "pending",
                    now if terminal else now + retry_delay_seconds,
                    error[:8000],
                    now,
                    task_id,
                ),
            )
            conn.execute("COMMIT")
        return True

    def get(self, task_id: str) -> TaskRecord | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        return None if row is None else self._row_to_record(row)

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> TaskRecord:
        return TaskRecord(
            id=row["id"],
            kind=row["kind"],
            payload=json.loads(row["payload_json"]),
            status=row["status"],
            attempts=row["attempts"],
            max_attempts=row["max_attempts"],
            available_at=row["available_at"],
            lease_owner=row["lease_owner"],
            lease_expires_at=row["lease_expires_at"],
            last_error=row["last_error"],
            result=None if row["result_json"] is None else json.loads(row["result_json"]),
        )
