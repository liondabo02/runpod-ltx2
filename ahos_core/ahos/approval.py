from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

from .governance import ActionRequest, AuthorityLevel, GovernancePolicy


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ApprovalEventType(str, Enum):
    REQUESTED = "requested"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class ApprovalRequest:
    request_id: str
    action: ActionRequest
    governance_reasons: tuple[str, ...]
    requested_at: str


@dataclass(frozen=True, slots=True)
class ApprovalDecision:
    request_id: str
    status: ApprovalStatus
    owner: str
    decided_at: str
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class ApprovalEvent:
    event_type: ApprovalEventType
    request_id: str
    action: ActionRequest
    timestamp: str
    governance_reasons: tuple[str, ...]
    owner: str | None = None
    reason: str | None = None


class ApprovalInbox:
    """Local append-only inbox for explicit owner decisions on C/D actions."""

    def __init__(
        self, path: str | Path = "approval_inbox.jsonl", policy: GovernancePolicy | None = None
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._policy = policy or GovernancePolicy()
        self.path.touch(exist_ok=True)

    def submit(self, action: ActionRequest) -> ApprovalRequest:
        if action.authority not in {AuthorityLevel.C, AuthorityLevel.D}:
            raise ValueError("approval inbox accepts only authority levels C and D")

        decision = self._policy.evaluate(action)
        if decision.allowed or not decision.owner_approval_required:
            raise ValueError("approval inbox accepts only blocked actions")

        request = ApprovalRequest(
            request_id=uuid4().hex,
            action=action,
            governance_reasons=decision.reasons,
            requested_at=_utc_now(),
        )
        self._append(
            ApprovalEvent(
                event_type=ApprovalEventType.REQUESTED,
                request_id=request.request_id,
                action=request.action,
                timestamp=request.requested_at,
                governance_reasons=request.governance_reasons,
            )
        )
        return request

    def pending(self) -> tuple[ApprovalRequest, ...]:
        requests: dict[str, ApprovalRequest] = {}
        for event in self.history():
            if event.event_type is ApprovalEventType.REQUESTED:
                requests[event.request_id] = ApprovalRequest(
                    request_id=event.request_id,
                    action=event.action,
                    governance_reasons=event.governance_reasons,
                    requested_at=event.timestamp,
                )
            else:
                requests.pop(event.request_id, None)
        return tuple(requests.values())

    def approve(
        self, request_id: str, owner: str, reason: str | None = None
    ) -> ApprovalDecision:
        return self._decide(request_id, owner, ApprovalStatus.APPROVED, reason)

    def reject(
        self, request_id: str, owner: str, reason: str | None = None
    ) -> ApprovalDecision:
        return self._decide(request_id, owner, ApprovalStatus.REJECTED, reason)

    def history(self) -> tuple[ApprovalEvent, ...]:
        events: list[ApprovalEvent] = []
        if not self.path.exists():
            return ()
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line:
                events.append(_event_from_record(json.loads(line)))
        return tuple(events)

    def _decide(
        self,
        request_id: str,
        owner: str,
        status: ApprovalStatus,
        reason: str | None,
    ) -> ApprovalDecision:
        owner = owner.strip()
        if not owner:
            raise ValueError("owner must not be empty")
        pending = {request.request_id: request for request in self.pending()}
        try:
            request = pending[request_id]
        except KeyError:
            raise KeyError(f"unknown or already decided approval {request_id!r}") from None

        decided_at = _utc_now()
        self._append(
            ApprovalEvent(
                event_type=ApprovalEventType(status.value),
                request_id=request.request_id,
                action=request.action,
                timestamp=decided_at,
                governance_reasons=request.governance_reasons,
                owner=owner,
                reason=reason,
            )
        )
        return ApprovalDecision(request_id, status, owner, decided_at, reason)

    def _append(self, event: ApprovalEvent) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(_event_to_record(event), sort_keys=True) + "\n")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _event_to_record(event: ApprovalEvent) -> dict[str, Any]:
    action = event.action
    return {
        "event_type": event.event_type.value,
        "request_id": event.request_id,
        "timestamp": event.timestamp,
        "governance_reasons": list(event.governance_reasons),
        "action": {
            "name": action.name,
            "authority": action.authority.value,
            "estimated_cost_usd": action.estimated_cost_usd,
            "external_side_effect": action.external_side_effect,
            "destructive": action.destructive,
            "touches_secrets": action.touches_secrets,
            "weakens_guardrails": action.weakens_guardrails,
        },
        "owner": event.owner,
        "reason": event.reason,
    }


def _event_from_record(record: dict[str, Any]) -> ApprovalEvent:
    action_record = record["action"]
    return ApprovalEvent(
        event_type=ApprovalEventType(record["event_type"]),
        request_id=record["request_id"],
        action=ActionRequest(
            name=action_record["name"],
            authority=AuthorityLevel(action_record["authority"]),
            estimated_cost_usd=action_record["estimated_cost_usd"],
            external_side_effect=action_record["external_side_effect"],
            destructive=action_record["destructive"],
            touches_secrets=action_record["touches_secrets"],
            weakens_guardrails=action_record["weakens_guardrails"],
        ),
        timestamp=record["timestamp"],
        governance_reasons=tuple(record["governance_reasons"]),
        owner=record.get("owner"),
        reason=record.get("reason"),
    )
