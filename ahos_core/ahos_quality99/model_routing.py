from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ModelEndpoint:
    name: str
    role: str
    estimated_cost_usd: float
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class RoutingDecision:
    allowed: bool
    builder: str | None
    reviewer: str | None
    blockers: tuple[str, ...]


class ZeroCostSeparationRouter:
    """Plan builder/reviewer separation without making any provider call."""

    def select(
        self,
        endpoints: tuple[ModelEndpoint, ...],
        *,
        preferred_builder: str | None = None,
        preferred_reviewer: str | None = None,
    ) -> RoutingDecision:
        blockers: list[str] = []
        usable = {
            row.name: row
            for row in endpoints
            if row.enabled and row.estimated_cost_usd == 0.0
        }

        builders = [row for row in usable.values() if row.role in {"builder", "both"}]
        reviewers = [row for row in usable.values() if row.role in {"reviewer", "both"}]

        builder = usable.get(preferred_builder) if preferred_builder else (builders[0] if builders else None)
        reviewer = usable.get(preferred_reviewer) if preferred_reviewer else next(
            (row for row in reviewers if builder is None or row.name != builder.name),
            None,
        )

        if builder is None or builder.role not in {"builder", "both"}:
            blockers.append("zero_cost_builder_unavailable")
        if reviewer is None or reviewer.role not in {"reviewer", "both"}:
            blockers.append("zero_cost_reviewer_unavailable")
        if builder is not None and reviewer is not None and builder.name == reviewer.name:
            blockers.append("builder_reviewer_not_separated")

        return RoutingDecision(
            allowed=not blockers,
            builder=builder.name if builder else None,
            reviewer=reviewer.name if reviewer else None,
            blockers=tuple(blockers),
        )
