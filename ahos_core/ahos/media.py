from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Mapping, Protocol, runtime_checkable

from .governance import ActionRequest, GovernanceDecision, GovernancePolicy


class MediaAuthorizationStatus(str, Enum):
    AUTHORIZED = "authorized"
    OWNER_APPROVAL_REQUIRED = "owner_approval_required"


class MediaExecutionStatus(str, Enum):
    NOT_EXECUTED = "not_executed"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class MediaRequest:
    """Immutable description of a media operation with its governance action."""

    request_id: str
    capability: str
    action: ActionRequest
    parameters: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.request_id, "request_id")
        _require_text(self.capability, "capability")
        object.__setattr__(self, "parameters", MappingProxyType(dict(self.parameters)))


@dataclass(frozen=True, slots=True)
class MediaAuthorization:
    """Governance state for a media request; it does not grant owner approval."""

    status: MediaAuthorizationStatus
    governance_reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", MediaAuthorizationStatus(self.status))
        object.__setattr__(self, "governance_reasons", tuple(self.governance_reasons))

    @classmethod
    def for_request(
        cls, request: MediaRequest, policy: GovernancePolicy | None = None
    ) -> MediaAuthorization:
        decision = (policy or GovernancePolicy()).evaluate(request.action)
        return cls.from_decision(decision)

    @classmethod
    def from_decision(cls, decision: GovernanceDecision) -> MediaAuthorization:
        if decision.allowed:
            return cls(MediaAuthorizationStatus.AUTHORIZED)
        return cls(
            MediaAuthorizationStatus.OWNER_APPROVAL_REQUIRED,
            decision.reasons,
        )

    @property
    def allowed(self) -> bool:
        return self.status is MediaAuthorizationStatus.AUTHORIZED


@dataclass(frozen=True, slots=True)
class MediaExecutionResult:
    """Immutable result envelope for an adapter operation."""

    request_id: str
    status: MediaExecutionStatus
    authorization: MediaAuthorization
    output_ref: str | None = None
    message: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.request_id, "request_id")
        object.__setattr__(self, "status", MediaExecutionStatus(self.status))


@runtime_checkable
class MediaCapabilityAdapter(Protocol):
    """Local contract for future media adapters."""

    def authorize(self, request: MediaRequest) -> MediaAuthorization:
        ...

    def execute(self, request: MediaRequest) -> MediaExecutionResult:
        ...


class InertMediaCapabilityAdapter:
    """Reference adapter that evaluates governance but never performs media work."""

    def __init__(self, policy: GovernancePolicy | None = None) -> None:
        self._policy = policy or GovernancePolicy()

    def authorize(self, request: MediaRequest) -> MediaAuthorization:
        return MediaAuthorization.for_request(request, self._policy)

    def execute(self, request: MediaRequest) -> MediaExecutionResult:
        authorization = self.authorize(request)
        if not authorization.allowed:
            return MediaExecutionResult(
                request_id=request.request_id,
                status=MediaExecutionStatus.REJECTED,
                authorization=authorization,
                message="owner approval is required; media execution was not started",
            )
        return MediaExecutionResult(
            request_id=request.request_id,
            status=MediaExecutionStatus.NOT_EXECUTED,
            authorization=authorization,
            message="inert adapter does not execute media operations",
        )


def _require_text(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must not be empty")
