from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AuthorityLevel(str, Enum):
    A = "A"  # observe / analyze
    B = "B"  # reversible local build/test
    C = "C"  # external action / spend / publish
    D = "D"  # privileged / destructive / authority change


@dataclass(frozen=True)
class ActionRequest:
    name: str
    authority: AuthorityLevel
    estimated_cost_usd: float = 0.0
    external_side_effect: bool = False
    destructive: bool = False
    touches_secrets: bool = False
    weakens_guardrails: bool = False


@dataclass(frozen=True)
class GovernanceDecision:
    allowed: bool
    owner_approval_required: bool
    reasons: tuple[str, ...]


class GovernancePolicy:
    """Immutable owner-control boundary for autonomous AHOS actions."""

    def evaluate(self, request: ActionRequest) -> GovernanceDecision:
        reasons: list[str] = []

        if request.weakens_guardrails:
            reasons.append("guardrail changes require owner approval")
        if request.touches_secrets:
            reasons.append("secret or credential access requires owner approval")
        if request.destructive:
            reasons.append("destructive action requires owner approval")
        if request.external_side_effect:
            reasons.append("external side effect requires owner approval")
        if request.estimated_cost_usd > 0:
            reasons.append("paid action requires owner approval")
        if request.authority in {AuthorityLevel.C, AuthorityLevel.D}:
            reasons.append(f"authority level {request.authority.value} requires owner approval")

        if reasons:
            return GovernanceDecision(
                allowed=False,
                owner_approval_required=True,
                reasons=tuple(dict.fromkeys(reasons)),
            )

        return GovernanceDecision(allowed=True, owner_approval_required=False, reasons=())
