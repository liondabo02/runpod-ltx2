from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Callable, Iterable, Protocol

from .mission_orchestrator import MissionResult, MissionStatus


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class QueueStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class QueuedMission:
    mission_id: str
    objective: str
    primary_department: str
    status: QueueStatus
    attempts: int
    max_attempts: int
    next_attempt_at: float
    lease_owner: str | None
    lease_until: float | None
    created_at: str
    updated_at: str
    last_error: str | None
    result_json: str | None


class MissionExecutor(Protocol):
    def __call__(self, mission: QueuedMission) -> MissionResult: ...


class PersistentMissionQueue:
    """SQLite-backed mission queue with leases and bounded retries.

    The queue itself performs no AI, network, publishing, payment, deployment,
    or credential action. It only persists and dispatches mission metadata.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS missions (
                    mission_id TEXT PRIMARY KEY,
                    objective TEXT NOT NULL,
                    primary_department TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    max_attempts INTEGER NOT NULL DEFAULT 1,
                    next_attempt_at REAL NOT NULL DEFAULT 0,
                    lease_owner TEXT,
                    lease_until REAL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_error TEXT,
                    result_json TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_missions_claim
                ON missions(status, next_attempt_at, created_at)
                """
            )

    def enqueue(
        self,
        *,
        mission_id: str,
        objective: str,
        primary_department: str,
        max_attempts: int = 1,
        replace_existing: bool = False,
    ) -> QueuedMission:
        mission_id = mission_id.strip()
        objective = objective.strip()
        primary_department = primary_department.strip().lower()

        if not mission_id:
            raise ValueError("mission_id must not be empty")
        if not objective:
            raise ValueError("objective must not be empty")
        if not primary_department:
            raise ValueError("primary_department must not be empty")
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")

        now = _utc_now()

        with self._connect() as conn:
            if replace_existing:
                conn.execute(
                    """
                    INSERT INTO missions (
                        mission_id, objective, primary_department, status,
                        attempts, max_attempts, next_attempt_at,
                        lease_owner, lease_until, created_at, updated_at,
                        last_error, result_json
                    )
                    VALUES (?, ?, ?, ?, 0, ?, 0, NULL, NULL, ?, ?, NULL, NULL)
                    ON CONFLICT(mission_id) DO UPDATE SET
                        objective=excluded.objective,
                        primary_department=excluded.primary_department,
                        status=excluded.status,
                        attempts=0,
                        max_attempts=excluded.max_attempts,
                        next_attempt_at=0,
                        lease_owner=NULL,
                        lease_until=NULL,
                        updated_at=excluded.updated_at,
                        last_error=NULL,
                        result_json=NULL
                    """,
                    (
                        mission_id,
                        objective,
                        primary_department,
                        QueueStatus.PENDING.value,
                        max_attempts,
                        now,
                        now,
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO missions (
                        mission_id, objective, primary_department, status,
                        attempts, max_attempts, next_attempt_at,
                        lease_owner, lease_until, created_at, updated_at,
                        last_error, result_json
                    )
                    VALUES (?, ?, ?, ?, 0, ?, 0, NULL, NULL, ?, ?, NULL, NULL)
                    """,
                    (
                        mission_id,
                        objective,
                        primary_department,
                        QueueStatus.PENDING.value,
                        max_attempts,
                        now,
                        now,
                    ),
                )

        mission = self.get(mission_id)
        assert mission is not None
        return mission

    def recover_expired_leases(self, *, now: float | None = None) -> int:
        now = time.time() if now is None else now
        updated_at = _utc_now()

        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE missions
                SET status=?,
                    lease_owner=NULL,
                    lease_until=NULL,
                    updated_at=?,
                    last_error=COALESCE(
                        last_error,
                        'recovered expired worker lease'
                    )
                WHERE status=?
                  AND lease_until IS NOT NULL
                  AND lease_until < ?
                """,
                (
                    QueueStatus.PENDING.value,
                    updated_at,
                    QueueStatus.RUNNING.value,
                    now,
                ),
            )
            return int(cursor.rowcount)

    def claim_next(
        self,
        *,
        owner: str,
        lease_seconds: int = 300,
        now: float | None = None,
    ) -> QueuedMission | None:
        owner = owner.strip()
        if not owner:
            raise ValueError("owner must not be empty")
        if lease_seconds < 1:
            raise ValueError("lease_seconds must be >= 1")

        now = time.time() if now is None else now
        lease_until = now + lease_seconds
        updated_at = _utc_now()

        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")

            # Recover stale RUNNING work before selecting a new item.
            conn.execute(
                """
                UPDATE missions
                SET status=?,
                    lease_owner=NULL,
                    lease_until=NULL,
                    updated_at=?,
                    last_error=COALESCE(
                        last_error,
                        'recovered expired worker lease'
                    )
                WHERE status=?
                  AND lease_until IS NOT NULL
                  AND lease_until < ?
                """,
                (
                    QueueStatus.PENDING.value,
                    updated_at,
                    QueueStatus.RUNNING.value,
                    now,
                ),
            )

            row = conn.execute(
                """
                SELECT mission_id
                FROM missions
                WHERE status=?
                  AND next_attempt_at <= ?
                  AND attempts < max_attempts
                ORDER BY created_at ASC, mission_id ASC
                LIMIT 1
                """,
                (QueueStatus.PENDING.value, now),
            ).fetchone()

            if row is None:
                conn.commit()
                return None

            mission_id = str(row["mission_id"])
            cursor = conn.execute(
                """
                UPDATE missions
                SET status=?,
                    attempts=attempts + 1,
                    lease_owner=?,
                    lease_until=?,
                    updated_at=?,
                    last_error=NULL
                WHERE mission_id=?
                  AND status=?
                """,
                (
                    QueueStatus.RUNNING.value,
                    owner,
                    lease_until,
                    updated_at,
                    mission_id,
                    QueueStatus.PENDING.value,
                ),
            )

            if cursor.rowcount != 1:
                conn.rollback()
                return None

            conn.commit()

        return self.get(mission_id)

    def complete(
        self,
        mission_id: str,
        *,
        owner: str,
        result: MissionResult,
    ) -> None:
        payload = self._result_payload(result)
        self._finish(
            mission_id,
            owner=owner,
            status=QueueStatus.COMPLETED,
            result_json=json.dumps(payload, ensure_ascii=False),
            last_error=None,
        )

    def block(
        self,
        mission_id: str,
        *,
        owner: str,
        result: MissionResult,
    ) -> None:
        payload = self._result_payload(result)
        self._finish(
            mission_id,
            owner=owner,
            status=QueueStatus.BLOCKED,
            result_json=json.dumps(payload, ensure_ascii=False),
            last_error=result.reason,
        )

    def fail(
        self,
        mission_id: str,
        *,
        owner: str,
        error: str,
        retry_delay_seconds: int = 30,
    ) -> QueueStatus:
        if retry_delay_seconds < 0:
            raise ValueError("retry_delay_seconds must be >= 0")

        mission = self.get(mission_id)
        if mission is None:
            raise KeyError(mission_id)
        if mission.status is not QueueStatus.RUNNING:
            raise RuntimeError(
                f"mission {mission_id} is not running: {mission.status.value}"
            )
        if mission.lease_owner != owner:
            raise RuntimeError(
                f"mission {mission_id} lease is owned by "
                f"{mission.lease_owner!r}, not {owner!r}"
            )

        final_status = (
            QueueStatus.PENDING
            if mission.attempts < mission.max_attempts
            else QueueStatus.FAILED
        )
        next_attempt_at = (
            time.time() + retry_delay_seconds
            if final_status is QueueStatus.PENDING
            else 0.0
        )

        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE missions
                SET status=?,
                    next_attempt_at=?,
                    lease_owner=NULL,
                    lease_until=NULL,
                    updated_at=?,
                    last_error=?
                WHERE mission_id=?
                  AND status=?
                  AND lease_owner=?
                """,
                (
                    final_status.value,
                    next_attempt_at,
                    _utc_now(),
                    error,
                    mission_id,
                    QueueStatus.RUNNING.value,
                    owner,
                ),
            )
            if cursor.rowcount != 1:
                raise RuntimeError(
                    f"mission {mission_id} could not be failed atomically"
                )

        return final_status

    def get(self, mission_id: str) -> QueuedMission | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM missions WHERE mission_id=?",
                (mission_id,),
            ).fetchone()

        return self._row_to_mission(row) if row is not None else None

    def list(
        self,
        *,
        statuses: Iterable[QueueStatus] | None = None,
    ) -> tuple[QueuedMission, ...]:
        with self._connect() as conn:
            if statuses is None:
                rows = conn.execute(
                    "SELECT * FROM missions ORDER BY created_at, mission_id"
                ).fetchall()
            else:
                values = tuple(status.value for status in statuses)
                if not values:
                    return ()
                placeholders = ",".join("?" for _ in values)
                rows = conn.execute(
                    f"""
                    SELECT *
                    FROM missions
                    WHERE status IN ({placeholders})
                    ORDER BY created_at, mission_id
                    """,
                    values,
                ).fetchall()

        return tuple(self._row_to_mission(row) for row in rows)

    def _finish(
        self,
        mission_id: str,
        *,
        owner: str,
        status: QueueStatus,
        result_json: str | None,
        last_error: str | None,
    ) -> None:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE missions
                SET status=?,
                    lease_owner=NULL,
                    lease_until=NULL,
                    updated_at=?,
                    last_error=?,
                    result_json=?
                WHERE mission_id=?
                  AND status=?
                  AND lease_owner=?
                """,
                (
                    status.value,
                    _utc_now(),
                    last_error,
                    result_json,
                    mission_id,
                    QueueStatus.RUNNING.value,
                    owner,
                ),
            )
            if cursor.rowcount != 1:
                raise RuntimeError(
                    f"mission {mission_id} could not be finalized atomically"
                )

    @staticmethod
    def _row_to_mission(row: sqlite3.Row) -> QueuedMission:
        return QueuedMission(
            mission_id=str(row["mission_id"]),
            objective=str(row["objective"]),
            primary_department=str(row["primary_department"]),
            status=QueueStatus(str(row["status"])),
            attempts=int(row["attempts"]),
            max_attempts=int(row["max_attempts"]),
            next_attempt_at=float(row["next_attempt_at"]),
            lease_owner=(
                str(row["lease_owner"])
                if row["lease_owner"] is not None
                else None
            ),
            lease_until=(
                float(row["lease_until"])
                if row["lease_until"] is not None
                else None
            ),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            last_error=(
                str(row["last_error"])
                if row["last_error"] is not None
                else None
            ),
            result_json=(
                str(row["result_json"])
                if row["result_json"] is not None
                else None
            ),
        )

    @staticmethod
    def _result_payload(result: MissionResult) -> dict[str, object]:
        return {
            "mission_id": result.mission_id,
            "objective": result.objective,
            "manager_id": result.manager_id,
            "status": result.status.value,
            "reason": result.reason,
            "steps": [
                {
                    "step_id": step.step.step_id,
                    "department": step.step.department,
                    "worker_id": step.worker_id,
                    "stage": step.stage.value,
                    "worker_summary": step.worker_summary,
                    "qa_summary": step.qa_summary,
                    "reason": step.reason,
                }
                for step in result.steps
            ],
        }


@dataclass(slots=True)
class CompanyLoop:
    queue: PersistentMissionQueue
    executor: MissionExecutor
    owner: str = "AHOS-COMPANY-LOOP"
    lease_seconds: int = 300
    retry_delay_seconds: int = 30

    def run_once(self) -> QueuedMission | None:
        mission = self.queue.claim_next(
            owner=self.owner,
            lease_seconds=self.lease_seconds,
        )
        if mission is None:
            return None

        try:
            result = self.executor(mission)
        except Exception as exc:
            self.queue.fail(
                mission.mission_id,
                owner=self.owner,
                error=f"{type(exc).__name__}: {exc}",
                retry_delay_seconds=self.retry_delay_seconds,
            )
            return self.queue.get(mission.mission_id)

        if result.status is MissionStatus.COMPLETED:
            self.queue.complete(
                mission.mission_id,
                owner=self.owner,
                result=result,
            )
        else:
            # BLOCKED missions never auto-retry. They require a human or
            # upstream state change, preserving the existing fail-closed model.
            self.queue.block(
                mission.mission_id,
                owner=self.owner,
                result=result,
            )

        return self.queue.get(mission.mission_id)

    def run_until_idle(
        self,
        *,
        max_cycles: int = 100,
    ) -> tuple[QueuedMission, ...]:
        if max_cycles < 1:
            raise ValueError("max_cycles must be >= 1")

        processed: list[QueuedMission] = []

        for _ in range(max_cycles):
            mission = self.run_once()
            if mission is None:
                break
            processed.append(mission)

            # A retry with a future next_attempt_at should not cause a busy loop.
            if mission.status is QueueStatus.PENDING:
                break

        return tuple(processed)

    def run_forever(
        self,
        *,
        poll_seconds: float = 2.0,
        should_stop: Callable[[], bool] | None = None,
    ) -> None:
        if poll_seconds <= 0:
            raise ValueError("poll_seconds must be > 0")

        should_stop = should_stop or (lambda: False)

        while not should_stop():
            mission = self.run_once()
            if mission is None:
                time.sleep(poll_seconds)
