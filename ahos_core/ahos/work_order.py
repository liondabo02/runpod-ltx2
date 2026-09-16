from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Iterable


class WorkOrderStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    BLOCKED = "blocked"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class WorkOrder:
    work_order_id: str
    venture_id: str
    mission_id: str
    capability_requirements: tuple[str, ...]
    priority: int
    dependencies: tuple[str, ...]
    budget_ceiling_usd: float
    routing_department: str | None
    routing_score: float | None
    status: WorkOrderStatus
    audit_correlation_id: str
    created_at: str
    updated_at: str

    def __post_init__(self) -> None:
        if not self.work_order_id.strip():
            raise ValueError("work_order_id must not be empty")
        if not self.venture_id.strip():
            raise ValueError("venture_id must not be empty")
        if not self.mission_id.strip():
            raise ValueError("mission_id must not be empty")
        if self.priority < 0:
            raise ValueError("priority must be >= 0")
        if self.budget_ceiling_usd < 0:
            raise ValueError("budget_ceiling_usd must be >= 0")
        if not self.audit_correlation_id.strip():
            raise ValueError("audit_correlation_id must not be empty")


_ALLOWED_TRANSITIONS: dict[WorkOrderStatus, frozenset[WorkOrderStatus]] = {
    WorkOrderStatus.PENDING: frozenset(
        {WorkOrderStatus.READY, WorkOrderStatus.BLOCKED, WorkOrderStatus.CANCELLED}
    ),
    WorkOrderStatus.READY: frozenset(
        {WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.BLOCKED, WorkOrderStatus.CANCELLED}
    ),
    WorkOrderStatus.BLOCKED: frozenset(
        {WorkOrderStatus.READY, WorkOrderStatus.CANCELLED}
    ),
    WorkOrderStatus.IN_PROGRESS: frozenset(
        {WorkOrderStatus.COMPLETED, WorkOrderStatus.FAILED, WorkOrderStatus.CANCELLED}
    ),
    WorkOrderStatus.FAILED: frozenset(
        {WorkOrderStatus.READY, WorkOrderStatus.CANCELLED}
    ),
    WorkOrderStatus.COMPLETED: frozenset(),
    WorkOrderStatus.CANCELLED: frozenset(),
}


class WorkOrderStore:
    """Persistent local-only work-order registry."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict[str, WorkOrder]:
        if not self.path.exists():
            return {}

        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("work order registry root must be a JSON object")

        result: dict[str, WorkOrder] = {}
        for work_order_id, item in raw.items():
            result[work_order_id] = WorkOrder(
                work_order_id=item["work_order_id"],
                venture_id=item["venture_id"],
                mission_id=item["mission_id"],
                capability_requirements=tuple(item.get("capability_requirements", ())),
                priority=int(item.get("priority", 0)),
                dependencies=tuple(item.get("dependencies", ())),
                budget_ceiling_usd=float(item.get("budget_ceiling_usd", 0.0)),
                routing_department=item.get("routing_department"),
                routing_score=(
                    float(item["routing_score"])
                    if item.get("routing_score") is not None
                    else None
                ),
                status=WorkOrderStatus(item["status"]),
                audit_correlation_id=item["audit_correlation_id"],
                created_at=item["created_at"],
                updated_at=item["updated_at"],
            )
        return result

    def _save(self, orders: dict[str, WorkOrder]) -> None:
        serializable: dict[str, dict[str, object]] = {}
        for work_order_id in sorted(orders):
            order = orders[work_order_id]
            record = asdict(order)
            record["status"] = order.status.value
            serializable[work_order_id] = record

        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(serializable, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        tmp.replace(self.path)

    def all(self) -> tuple[WorkOrder, ...]:
        orders = self._load()
        return tuple(orders[key] for key in sorted(orders))

    def get(self, work_order_id: str) -> WorkOrder | None:
        return self._load().get(work_order_id)

    def create(
        self,
        *,
        work_order_id: str,
        venture_id: str,
        mission_id: str,
        capability_requirements: Iterable[str] = (),
        priority: int = 0,
        dependencies: Iterable[str] = (),
        budget_ceiling_usd: float = 0.0,
        routing_department: str | None = None,
        routing_score: float | None = None,
        audit_correlation_id: str | None = None,
        timestamp: str | None = None,
    ) -> WorkOrder:
        orders = self._load()
        if work_order_id in orders:
            raise ValueError(f"duplicate work_order_id: {work_order_id}")

        when = timestamp or datetime.now(timezone.utc).isoformat()
        order = WorkOrder(
            work_order_id=work_order_id,
            venture_id=venture_id,
            mission_id=mission_id,
            capability_requirements=tuple(dict.fromkeys(capability_requirements)),
            priority=priority,
            dependencies=tuple(dict.fromkeys(dependencies)),
            budget_ceiling_usd=float(budget_ceiling_usd),
            routing_department=routing_department,
            routing_score=float(routing_score) if routing_score is not None else None,
            status=WorkOrderStatus.PENDING,
            audit_correlation_id=audit_correlation_id or f"work-order:{work_order_id}",
            created_at=when,
            updated_at=when,
        )
        orders[work_order_id] = order
        self._save(orders)
        return order

    def transition(
        self,
        work_order_id: str,
        to_status: WorkOrderStatus,
        *,
        timestamp: str | None = None,
    ) -> WorkOrder:
        orders = self._load()
        current = orders.get(work_order_id)
        if current is None:
            raise KeyError(f"unknown work_order_id: {work_order_id}")

        if to_status is current.status:
            raise ValueError("work order is already in requested status")

        if to_status not in _ALLOWED_TRANSITIONS[current.status]:
            raise ValueError(
                f"invalid work order transition: {current.status.value} -> {to_status.value}"
            )

        updated = replace(
            current,
            status=to_status,
            updated_at=timestamp or datetime.now(timezone.utc).isoformat(),
        )
        orders[work_order_id] = updated
        self._save(orders)
        return updated

    def ready(
        self,
        completed_work_order_ids: Iterable[str] = (),
    ) -> tuple[WorkOrder, ...]:
        completed = set(completed_work_order_ids)
        orders = self.all()
        ready: list[WorkOrder] = []

        for order in orders:
            if order.status not in {WorkOrderStatus.PENDING, WorkOrderStatus.READY}:
                continue
            if all(dep in completed for dep in order.dependencies):
                ready.append(order)

        ready.sort(key=lambda item: (-item.priority, item.work_order_id))
        return tuple(ready)
