from __future__ import annotations

from dataclasses import dataclass

from .maturity import MaturityReport
from .requirement_audit import RequirementAudit
from .runtime_audit import RuntimeAuditReport


@dataclass(frozen=True, slots=True)
class FinalReadinessReport:
    target_score: float
    effective_score: float
    ready: bool
    blockers: tuple[str, ...]


class FinalReadinessEvaluator:
    """Fail-closed AHOS 99% acceptance gate.

    This evaluator intentionally separates source completeness from production
    evidence. It can only report ready when the requirement audit, maturity
    proof gates, and runtime health all agree.
    """

    def __init__(self, target_score: float = 99.0) -> None:
        if not 0 < target_score <= 100:
            raise ValueError("target_score must be in (0, 100]")
        self.target_score = float(target_score)

    def evaluate(
        self,
        *,
        requirements: RequirementAudit,
        maturity: MaturityReport,
        runtime: RuntimeAuditReport,
    ) -> FinalReadinessReport:
        blockers: list[str] = []

        if not requirements.platform_ready:
            blockers.append("platform_requirements_not_proven")
        if not requirements.department_acceptance_ready:
            blockers.append("department_acceptance_not_proven")
        if not runtime.healthy:
            blockers.extend(f"runtime:{item}" for item in runtime.blockers)
        if maturity.blockers:
            blockers.extend(f"maturity:{item}" for item in maturity.blockers)
        if maturity.score < self.target_score:
            blockers.append(
                f"maturity_score_below_target:{maturity.score:.2f}<{self.target_score:.2f}"
            )

        effective_score = maturity.score
        if not requirements.platform_ready:
            effective_score = min(effective_score, 90.0)
        if not requirements.department_acceptance_ready:
            effective_score = min(effective_score, 96.0)
        if not runtime.healthy:
            effective_score = min(effective_score, 97.0)

        unique_blockers = tuple(sorted(set(blockers)))
        ready = not unique_blockers and effective_score >= self.target_score
        return FinalReadinessReport(
            target_score=self.target_score,
            effective_score=round(effective_score, 2),
            ready=ready,
            blockers=unique_blockers,
        )
