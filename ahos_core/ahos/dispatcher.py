from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .governance import AuthorityLevel
from .routing import DepartmentRoutingEngine, RoutingDecision


class DispatchState(str, Enum):
    READY = "ready"
    BLOCKED = "blocked"
    WAITING_APPROVAL = "waiting_approval"
    RETRYABLE = "retryable"
    COMPLETED = "completed"
    FAILED = "failed"
    TERMINAL = "terminal"


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    attempt: int = 0
    max_attempts: int = 1

    def __post_init__(self) -> None:
        if self.attempt < 0:
            raise ValueError("attempt must be >= 0")
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")


@dataclass(frozen=True, slots=True)
class AuditMetadata:
    correlation_id: str
    event_type: str = "mission.dispatch"


@dataclass(frozen=True, slots=True)
class MissionExecutionEnvelope:
    mission_id: str
    mission_state: str
    dependency_ready: bool
    routing: RoutingDecision
    owner_approval_required: bool
    approval_status: str | None
    retry_policy: RetryPolicy
    audit: AuditMetadata
    execution_result_state: str | None
    dispatch_state: DispatchState
    reasons: tuple[str, ...]

    @property
    def dispatchable(self) -> bool:
        return self.dispatch_state is DispatchState.READY


class MissionDispatcher:
    """Build inert, local-only mission execution envelopes.

    This component does not execute a mission. It only combines already-known
    mission/dependency/governance/retry/audit facts with deterministic routing
    into a decision envelope that a later executor can consume safely.
    """

    TERMINAL_MISSION_STATES = frozenset({"completed", "cancelled", "failed"})

    def __init__(self, routing_engine: DepartmentRoutingEngine | None = None) -> None:
        self.routing_engine = routing_engine or DepartmentRoutingEngine()

    def build_envelope(
        self,
        mission_id: str,
        objective: str,
        *,
        mission_state: str = "ready",
        dependency_ready: bool = True,
        required_capabilities: tuple[str, ...] = (),
        max_authority: AuthorityLevel = AuthorityLevel.B,
        owner_approval_required: bool = False,
        approval_status: str | None = None,
        attempt: int = 0,
        max_attempts: int = 1,
        audit_correlation_id: str | None = None,
        execution_result_state: str | None = None,
    ) -> MissionExecutionEnvelope:
        retry = RetryPolicy(attempt=attempt, max_attempts=max_attempts)
        routing = self.routing_engine.route_mission(
            mission_id,
            objective,
            required_capabilities=required_capabilities,
            max_authority=max_authority,
        )
        audit = AuditMetadata(
            correlation_id=audit_correlation_id or f"mission:{mission_id}"
        )

        normalized_mission_state = mission_state.strip().lower()
        normalized_approval = approval_status.strip().lower() if approval_status else None
        normalized_result = (
            execution_result_state.strip().lower()
            if execution_result_state
            else None
        )

        reasons: list[str] = []

        if normalized_result == "completed":
            state = DispatchState.COMPLETED
            reasons.append("execution already completed")
        elif normalized_result == "failed" and retry.attempt >= retry.max_attempts:
            state = DispatchState.FAILED
            reasons.append("retry budget exhausted")
        elif normalized_result == "failed":
            state = DispatchState.RETRYABLE
            reasons.append("previous execution failed and retry budget remains")
        elif normalized_mission_state in self.TERMINAL_MISSION_STATES:
            state = DispatchState.TERMINAL
            reasons.append(f"mission state is terminal: {normalized_mission_state}")
        elif not dependency_ready:
            state = DispatchState.BLOCKED
            reasons.append("mission dependencies are not ready")
        elif routing.blocked_capabilities:
            state = DispatchState.BLOCKED
            reasons.append(
                "required capabilities exceed authority ceiling: "
                + ", ".join(routing.blocked_capabilities)
            )
        elif routing.unmatched_required_capabilities:
            state = DispatchState.BLOCKED
            reasons.append(
                "required capabilities are unavailable: "
                + ", ".join(routing.unmatched_required_capabilities)
            )
        elif routing.primary is None:
            state = DispatchState.BLOCKED
            reasons.append("no department routing candidate is available")
        elif owner_approval_required and normalized_approval != "approved":
            state = DispatchState.WAITING_APPROVAL
            reasons.append("owner approval is required before dispatch")
        else:
            state = DispatchState.READY
            reasons.append(
                f"ready for inert handoff to {routing.primary.department.value}"
            )

        return MissionExecutionEnvelope(
            mission_id=mission_id,
            mission_state=mission_state,
            dependency_ready=dependency_ready,
            routing=routing,
            owner_approval_required=owner_approval_required,
            approval_status=approval_status,
            retry_policy=retry,
            audit=audit,
            execution_result_state=execution_result_state,
            dispatch_state=state,
            reasons=tuple(reasons),
        )
