from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum

from .github_research import GitHubRepositoryEvidence


class LicenseDisposition(str, Enum):
    ALLOW_WITH_REVIEW = "allow_with_review"
    CONDITIONAL = "conditional"
    OWNER_OR_LEGAL = "owner_or_legal"
    BLOCK = "block"


class EvaluationRecommendation(str, Enum):
    REJECT = "reject"
    HOLD = "hold"
    ASSESS = "assess"
    TRIAL = "trial"


@dataclass(frozen=True, slots=True)
class TechnologySignals:
    repository: GitHubRepositoryEvidence
    days_since_push: int | None
    open_critical_vulnerabilities: int | None
    security_policy_present: bool | None
    sbom_present: bool | None
    secret_scan_passed: bool | None
    unexplained_binaries: bool | None
    relevance_score: int


@dataclass(frozen=True, slots=True)
class TechnologyEvaluation:
    technology_id: str
    source_sha: str | None
    license_spdx: str | None
    license_disposition: LicenseDisposition
    maintenance_score: int
    security_score: int
    relevance_score: int
    total_score: int
    blockers: tuple[str, ...]
    recommendation: EvaluationRecommendation
    requires_owner_approval: bool
    eligible_for_sandbox_proposal: bool

    def to_payload(self) -> dict[str, object]:
        payload = asdict(self)
        payload["schema"] = "ahos.technology-evaluation.v1"
        payload["license_disposition"] = self.license_disposition.value
        payload["recommendation"] = self.recommendation.value
        return payload


class TechnologyEvaluator:
    ALLOW = frozenset({"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC"})
    CONDITIONAL = frozenset({"MPL-2.0", "LGPL-2.1-only", "LGPL-2.1-or-later", "LGPL-3.0-only", "LGPL-3.0-or-later"})
    OWNER = frozenset({"GPL-2.0-only", "GPL-2.0-or-later", "GPL-3.0-only", "GPL-3.0-or-later", "AGPL-3.0-only", "AGPL-3.0-or-later", "SSPL-1.0", "proprietary"})

    def evaluate(self, *, technology_id: str, signals: TechnologySignals) -> TechnologyEvaluation:
        if not 0 <= signals.relevance_score <= 100:
            raise ValueError("relevance_score must be 0..100")
        lic = signals.repository.license_spdx
        disposition = LicenseDisposition.ALLOW_WITH_REVIEW if lic in self.ALLOW else LicenseDisposition.CONDITIONAL if lic in self.CONDITIONAL else LicenseDisposition.OWNER_OR_LEGAL if lic in self.OWNER else LicenseDisposition.BLOCK
        days = signals.days_since_push
        maintenance = 0 if days is None else 100 if days <= 90 else 85 if days <= 180 else 65 if days <= 365 else 35 if days <= 730 else 10
        security = 100
        blockers = []
        if not signals.repository.head_sha:
            blockers.append("missing_immutable_commit")
        if disposition is LicenseDisposition.BLOCK:
            blockers.append("license_blocked_or_unknown")
        if days is None or maintenance < 60:
            blockers.append("maintenance_insufficient")
        if signals.open_critical_vulnerabilities is None:
            blockers.append("vulnerability_evidence_missing")
            security -= 40
        elif signals.open_critical_vulnerabilities > 0:
            blockers.append("critical_vulnerability")
            security = 0
        for name, value in (("security_policy", signals.security_policy_present), ("sbom", signals.sbom_present), ("secret_scan", signals.secret_scan_passed)):
            if value is not True:
                blockers.append(f"{name}_evidence_missing")
                security -= 20
        if signals.unexplained_binaries is not False:
            blockers.append("unexplained_binary_or_unknown")
            security = 0
        if signals.relevance_score < 60:
            blockers.append("relevance_insufficient")
        security = max(0, security)
        total = round(maintenance * .35 + security * .40 + signals.relevance_score * .25)
        eligible = not blockers
        owner = disposition in {LicenseDisposition.CONDITIONAL, LicenseDisposition.OWNER_OR_LEGAL}
        recommendation = EvaluationRecommendation.REJECT if blockers else EvaluationRecommendation.HOLD if owner else EvaluationRecommendation.TRIAL if total >= 80 else EvaluationRecommendation.ASSESS
        return TechnologyEvaluation(technology_id, signals.repository.head_sha, lic, disposition, maintenance, security, signals.relevance_score, total, tuple(blockers), recommendation, owner, eligible)
