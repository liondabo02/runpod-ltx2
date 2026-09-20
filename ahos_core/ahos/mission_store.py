from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Iterator


class MissionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class Mission:
    mission_id: str
    status: MissionStatus
    created_at: str
    updated_at: str


_SCHEMA = """
CREATE TABLE IF NOT EXISTS missions (
    mission_id TEXT PRIMARY KEY,
    status TEXT NOT NULL CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


class MissionStateStore:
    """Persistent local SQLite storage for mission lifecycle state."""

    def __init__(self, path: str | Path = "ahos.db") -> None:
        self.path = path
        self._memory_connection = (
            sqlite3.connect(":memory:") if str(path) == ":memory:" else None
        )
        if self._memory_connection is None:
            database_path = Path(path)
            database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(_SCHEMA)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = self._memory_connection or sqlite3.connect(self.path)
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            if self._memory_connection is None:
                connection.close()

    def create_mission(
        self, mission_id: str, status: MissionStatus = MissionStatus.PENDING
    ) -> Mission:
        mission_status = MissionStatus(status)
        now = _utc_now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO missions(mission_id, status, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (mission_id, mission_status.value, now, now),
            )
        return Mission(mission_id, mission_status, now, now)

    def read_mission(self, mission_id: str) -> Mission | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT mission_id, status, created_at, updated_at
                FROM missions
                WHERE mission_id = ?
                """,
                (mission_id,),
            ).fetchone()
        return _mission_from_row(row)

    def update_mission(self, mission_id: str, status: MissionStatus) -> Mission | None:
        mission_status = MissionStatus(status)
        now = _utc_now()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE missions
                SET status = ?, updated_at = ?
                WHERE mission_id = ?
                """,
                (mission_status.value, now, mission_id),
            )
            if cursor.rowcount == 0:
                return None
        return self.read_mission(mission_id)

    def close(self) -> None:
        if self._memory_connection is not None:
            self._memory_connection.close()
            self._memory_connection = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mission_from_row(row: tuple[str, str, str, str] | None) -> Mission | None:
    if row is None:
        return None
    return Mission(
        mission_id=row[0],
        status=MissionStatus(row[1]),
        created_at=row[2],
        updated_at=row[3],
    )
