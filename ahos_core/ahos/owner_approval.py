from __future__ import annotations

import sqlite3
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Iterable

from .mission_orchestrator import (
    ManagerPlanner,
    MissionStepSpec,
    OwnerApprovalPending,
    OwnerApprovalRejected,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ApprovalStatus(str, Enum):
    WAITING_OWNER_APPROVAL = "waiting_owner_approval"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class ApprovalRequest:
    request_id: str
    mission_id: str
    step_id: str
    title: str
    estimated_cost_usd: float
    external_side_effect: bool
    destructive: bool
    touches_secrets: bool
    status: ApprovalStatus
    created_at: str
    decided_at: str | None


class OwnerApprovalInbox:
    """Persistent local owner-approval inbox. No network or AI calls."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS approval_requests (
                    request_id TEXT PRIMARY KEY,
                    mission_id TEXT NOT NULL,
                    step_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    estimated_cost_usd REAL NOT NULL,
                    external_side_effect INTEGER NOT NULL,
                    destructive INTEGER NOT NULL,
                    touches_secrets INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    decided_at TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_approval_status_created
                ON approval_requests(status, created_at, request_id)
                """
            )

    @staticmethod
    def requires_approval(step: MissionStepSpec) -> bool:
        return any(
            (
                step.requires_owner_approval,
                step.external_side_effect,
                step.destructive,
                step.touches_secrets,
                step.estimated_cost_usd > 0,
            )
        )

    def ensure_for_step(
        self,
        mission_id: str,
        step: MissionStepSpec,
    ) -> ApprovalRequest | None:
        if not self.requires_approval(step):
            return None

        request_id = f"{mission_id}:{step.step_id}"
        now = _utc_now()

        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO approval_requests (
                    request_id, mission_id, step_id, title,
                    estimated_cost_usd, external_side_effect,
                    destructive, touches_secrets,
                    status, created_at, decided_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    request_id,
                    mission_id,
                    step.step_id,
                    step.title,
                    step.estimated_cost_usd,
                    int(step.external_side_effect),
                    int(step.destructive),
                    int(step.touches_secrets),
                    ApprovalStatus.WAITING_OWNER_APPROVAL.value,
                    now,
                ),
            )

        request = self.get(request_id)
        assert request is not None
        return request

    def get(self, request_id: str) -> ApprovalRequest | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM approval_requests WHERE request_id=?",
                (request_id,),
            ).fetchone()
        return self._row(row) if row is not None else None

    def list_waiting(self) -> tuple[ApprovalRequest, ...]:
        return self.list(statuses=(ApprovalStatus.WAITING_OWNER_APPROVAL,))

    def list(
        self,
        *,
        statuses: Iterable[ApprovalStatus] | None = None,
    ) -> tuple[ApprovalRequest, ...]:
        with self._connect() as conn:
            if statuses is None:
                rows = conn.execute(
                    "SELECT * FROM approval_requests ORDER BY created_at, request_id"
                ).fetchall()
            else:
                values = tuple(status.value for status in statuses)
                if not values:
                    return ()
                placeholders = ",".join("?" for _ in values)
                rows = conn.execute(
                    f"""
                    SELECT * FROM approval_requests
                    WHERE status IN ({placeholders})
                    ORDER BY created_at, request_id
                    """,
                    values,
                ).fetchall()
        return tuple(self._row(row) for row in rows)

    def approve(self, request_id: str) -> ApprovalRequest:
        return self._decide(request_id, ApprovalStatus.APPROVED)

    def reject(self, request_id: str) -> ApprovalRequest:
        return self._decide(request_id, ApprovalStatus.REJECTED)

    def _decide(self, request_id: str, status: ApprovalStatus) -> ApprovalRequest:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE approval_requests
                SET status=?, decided_at=?
                WHERE request_id=? AND status=?
                """,
                (
                    status.value,
                    _utc_now(),
                    request_id,
                    ApprovalStatus.WAITING_OWNER_APPROVAL.value,
                ),
            )
            if cursor.rowcount != 1:
                current = self.get(request_id)
                if current is None:
                    raise KeyError(request_id)
                if current.status is status:
                    return current
                raise RuntimeError(
                    f"approval request {request_id} is already {current.status.value}"
                )

        decided = self.get(request_id)
        assert decided is not None
        return decided

    @staticmethod
    def _row(row: sqlite3.Row) -> ApprovalRequest:
        return ApprovalRequest(
            request_id=str(row["request_id"]),
            mission_id=str(row["mission_id"]),
            step_id=str(row["step_id"]),
            title=str(row["title"]),
            estimated_cost_usd=float(row["estimated_cost_usd"]),
            external_side_effect=bool(row["external_side_effect"]),
            destructive=bool(row["destructive"]),
            touches_secrets=bool(row["touches_secrets"]),
            status=ApprovalStatus(str(row["status"])),
            created_at=str(row["created_at"]),
            decided_at=(
                str(row["decided_at"]) if row["decided_at"] is not None else None
            ),
        )


@dataclass(slots=True)
class ApprovalAwareManagerPlanner:
    """Wrap a manager planner with a persistent human approval gate."""

    delegate: ManagerPlanner
    inbox: OwnerApprovalInbox

    def __call__(
        self,
        mission_id: str,
        objective: str,
        manager_id: str,
    ) -> Iterable[MissionStepSpec]:
        steps = tuple(self.delegate(mission_id, objective, manager_id))

        protected: list[tuple[MissionStepSpec, ApprovalRequest]] = []
        for step in steps:
            request = self.inbox.ensure_for_step(mission_id, step)
            if request is not None:
                protected.append((step, request))

        rejected = [
            request.request_id
            for _, request in protected
            if request.status is ApprovalStatus.REJECTED
        ]
        if rejected:
            raise OwnerApprovalRejected(
                "owner rejected protected work: " + ", ".join(rejected)
            )

        waiting = [
            request.request_id
            for _, request in protected
            if request.status is ApprovalStatus.WAITING_OWNER_APPROVAL
        ]
        if waiting:
            raise OwnerApprovalPending(
                "waiting for owner approval: " + ", ".join(waiting)
            )

        approved_ids = {
            request.request_id
            for _, request in protected
            if request.status is ApprovalStatus.APPROVED
        }

        return tuple(
            replace(step, owner_approved=True)
            if f"{mission_id}:{step.step_id}" in approved_ids
            else step
            for step in steps
        )
