from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .final_readiness import FinalReadinessEvaluator, FinalReadinessReport
from .maturity import CapabilityEvidence, CapabilityState, MaturityReport, evaluate_maturity
from .production_proof_gate import ProofBundleReport
from .requirement_audit import RequirementAudit, audit_requirements
from .runtime_audit import RuntimeAuditReport
from .verification_baseline import VerificationBaseline


CANONICAL_REQUIREMENTS = {
    "HOLDING": "holding platform",
    "CODING": "coding reliability",
    "RELIABILITY": "runtime health and recovery",
    "STUDIO": "studio acceptance",
    "IDENTITY": "identity acceptance",
    "LANGUAGES": "language acceptance",
    "OWNER_GATES": "owner approval gates",
    "EVIDENCE": "evidence integrity",
}

MATURITY_WEIGHTS = {
    "holding_platform": 14,
    "coding_reliability": 12,
    "runtime_health": 12,
    "owner_gates": 10,
    "evidence": 10,
    "studio_acceptance": 12,
    "identity_acceptance": 8,
    "language_acceptance": 8,
    "deployment_proof": 5,
    "autonomous_runtime_proof": 5,
    "recovery_proof": 4,
}


@dataclass(frozen=True, slots=True)
class AcceptanceControllerReport:
    ready: bool
    score: float
    final: FinalReadinessReport
    requirements: RequirementAudit
    maturity: MaturityReport
    blockers: tuple[str, ...]

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": "ahos.acceptance-controller.v1",
            "ready": self.ready,
            "score": self.score,
            "blockers": list(self.blockers),
            "final": {
                "target_score": self.final.target_score,
                "effective_score": self.final.effective_score,
                "ready": self.final.ready,
                "blockers": list(self.final.blockers),
            },
            "requirements": {
                "platform_ready": self.requirements.platform_ready,
                "department_acceptance_ready": self.requirements.department_acceptance_ready,
                "rows": list(self.requirements.rows),
            },
            "maturity": {
                "score": self.maturity.score,
                "raw_score": self.maturity.raw_score,
                "blockers": list(self.maturity.blockers),
            },
        }


class AcceptanceController:
    """Compose independently verified AHOS evidence into one final readiness result."""

    def __init__(self, *, target_score: float = 99.0) -> None:
        self.final_gate = FinalReadinessEvaluator(target_score=target_score)

    def evaluate(
        self,
        *,
        core_baseline: VerificationBaseline,
        production_proofs: ProofBundleReport,
        runtime: RuntimeAuditReport,
        verified_at: datetime | None = None,
    ) -> AcceptanceControllerReport:
        blockers: list[str] = []
        if not production_proofs.ready:
            blockers.extend(f"production:{item}" for item in production_proofs.blockers)
        if core_baseline.commit_sha != production_proofs.commit_sha:
            blockers.append("evidence_commit_mismatch")
        if core_baseline.platform != production_proofs.platform:
            blockers.append("evidence_platform_mismatch")

        combined_proofs = set(core_baseline.proofs)
        combined_proofs.update(production_proofs.proven)
        if runtime.healthy:
            combined_proofs.add("runtime_health")

        baseline = VerificationBaseline(
            verified_at=(verified_at or datetime.now(timezone.utc)).astimezone(timezone.utc),
            commit_sha=core_baseline.commit_sha,
            platform=core_baseline.platform,
            proofs=frozenset(combined_proofs),
        )
        requirements = audit_requirements(CANONICAL_REQUIREMENTS, baseline)

        capabilities = tuple(
            CapabilityEvidence(
                name=name,
                weight=weight,
                state=CapabilityState.PROVEN if name in combined_proofs else CapabilityState.MISSING,
                evidence="verified proof" if name in combined_proofs else "missing proof",
            )
            for name, weight in MATURITY_WEIGHTS.items()
        )
        maturity = evaluate_maturity(capabilities)
        final = self.final_gate.evaluate(
            requirements=requirements,
            maturity=maturity,
            runtime=runtime,
        )
        blockers.extend(final.blockers)
        unique = tuple(sorted(set(blockers)))
        return AcceptanceControllerReport(
            ready=not unique and final.ready,
            score=final.effective_score,
            final=final,
            requirements=requirements,
            maturity=maturity,
            blockers=unique,
        )
