from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from .governance import AuthorityLevel
from .registry import Department, DepartmentCapabilityRegistry


_AUTHORITY_RANK = {
    AuthorityLevel.A: 0,
    AuthorityLevel.B: 1,
    AuthorityLevel.C: 2,
    AuthorityLevel.D: 3,
}

_STOP_WORDS = {
    "and",
    "the",
    "for",
    "with",
    "from",
    "into",
    "only",
    "local",
    "mission",
    "available",
}


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", value.lower().replace("_", " ").replace(".", " "))
        if len(token) >= 3 and token not in _STOP_WORDS
    }


@dataclass(frozen=True, slots=True)
class RoutingRequest:
    mission_id: str
    objective: str
    required_capabilities: tuple[str, ...] = ()
    max_authority: AuthorityLevel = AuthorityLevel.B


@dataclass(frozen=True, slots=True)
class RoutingCandidate:
    department: Department
    score: int
    matched_capabilities: tuple[str, ...]
    highest_authority: AuthorityLevel
    explanation: str


@dataclass(frozen=True, slots=True)
class RoutingDecision:
    mission_id: str
    candidates: tuple[RoutingCandidate, ...]
    blocked_capabilities: tuple[str, ...]
    unmatched_required_capabilities: tuple[str, ...]

    @property
    def primary(self) -> RoutingCandidate | None:
        return self.candidates[0] if self.candidates else None


class DepartmentRoutingEngine:
    """Deterministic, local-only AHOS department routing.

    The engine performs no external actions and makes no network or model calls.
    Exact requested capabilities receive the strongest score. Objective-token
    overlap provides a deterministic secondary signal. Capabilities above the
    request's authority ceiling are excluded and reported as blocked.
    """

    def __init__(self, registry: DepartmentCapabilityRegistry | None = None) -> None:
        self.registry = registry or DepartmentCapabilityRegistry()

    @staticmethod
    def _allowed(authority: AuthorityLevel, ceiling: AuthorityLevel) -> bool:
        return _AUTHORITY_RANK[authority] <= _AUTHORITY_RANK[ceiling]

    def route(self, request: RoutingRequest) -> RoutingDecision:
        required = tuple(dict.fromkeys(request.required_capabilities))
        objective_tokens = _tokens(request.objective)

        blocked: list[str] = []
        unmatched: list[str] = []

        for capability_name in required:
            capability = self.registry.get(capability_name)
            if capability is None:
                unmatched.append(capability_name)
            elif not self._allowed(capability.authority, request.max_authority):
                blocked.append(capability_name)

        department_matches: dict[Department, list[tuple[str, int, AuthorityLevel]]] = {}

        for department in self.registry.departments:
            matches: list[tuple[str, int, AuthorityLevel]] = []

            for capability in self.registry.capabilities_for(department):
                if not self._allowed(capability.authority, request.max_authority):
                    continue

                score = 0
                if capability.name in required:
                    score += 100

                haystack_tokens = _tokens(f"{capability.name} {capability.description}")
                overlap = objective_tokens.intersection(haystack_tokens)
                score += len(overlap) * 10

                if score > 0:
                    matches.append((capability.name, score, capability.authority))

            if matches:
                department_matches[department] = matches

        candidates: list[RoutingCandidate] = []
        for department, matches in department_matches.items():
            matches.sort(key=lambda item: (-item[1], item[0]))
            score = sum(item[1] for item in matches)
            highest_authority = max(
                (item[2] for item in matches),
                key=lambda authority: _AUTHORITY_RANK[authority],
            )
            matched_names = tuple(item[0] for item in matches)
            explanation = (
                f"{department.value}: score={score}; "
                f"matched={', '.join(matched_names)}; "
                f"authority<={request.max_authority.value}"
            )
            candidates.append(
                RoutingCandidate(
                    department=department,
                    score=score,
                    matched_capabilities=matched_names,
                    highest_authority=highest_authority,
                    explanation=explanation,
                )
            )

        candidates.sort(key=lambda item: (-item.score, str(item.department.value)))

        return RoutingDecision(
            mission_id=request.mission_id,
            candidates=tuple(candidates),
            blocked_capabilities=tuple(blocked),
            unmatched_required_capabilities=tuple(unmatched),
        )

    def route_mission(
        self,
        mission_id: str,
        objective: str,
        *,
        required_capabilities: Iterable[str] = (),
        max_authority: AuthorityLevel = AuthorityLevel.B,
    ) -> RoutingDecision:
        return self.route(
            RoutingRequest(
                mission_id=mission_id,
                objective=objective,
                required_capabilities=tuple(required_capabilities),
                max_authority=max_authority,
            )
        )
