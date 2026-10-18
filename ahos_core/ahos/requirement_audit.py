from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .verification_baseline import VerificationBaseline


REQUIREMENT_PROOFS: dict[str, frozenset[str]] = {
    "HOLDING": frozenset({"holding_platform"}),
    "CODING": frozenset({"coding_reliability"}),
    "RELIABILITY": frozenset({"runtime_health", "recovery"}),
    "STUDIO": frozenset({"studio_acceptance"}),
    "IDENTITY": frozenset({"identity_acceptance"}),
    "LANGUAGES": frozenset({"language_acceptance"}),
    "OWNER_GATES": frozenset({"owner_gates"}),
    "EVIDENCE": frozenset({"evidence"}),
}

PLATFORM_REQUIREMENTS = frozenset({
    "HOLDING", "CODING", "RELIABILITY", "OWNER_GATES", "EVIDENCE"
})
DEPARTMENT_ACCEPTANCE_REQUIREMENTS = frozenset({
    "STUDIO", "IDENTITY", "LANGUAGES"
})


@dataclass(frozen=True, slots=True)
class RequirementAudit:
    rows: tuple[dict[str, str], ...]
    platform_ready: bool
    department_acceptance_ready: bool


def audit_requirements(requirements: Mapping[str, str], baseline: VerificationBaseline | None) -> RequirementAudit:
    rows: list[dict[str, str]] = []
    status_by_id: dict[str, str] = {}
    for requirement_id, requirement in requirements.items():
        needed = REQUIREMENT_PROOFS.get(requirement_id, frozenset())
        if baseline is None:
            status = "not_audited"
        elif needed and needed.issubset(baseline.proofs):
            status = "proven"
        else:
            status = "not_proven"
        status_by_id[requirement_id] = status
        rows.append({
            "id": requirement_id,
            "requirement": requirement,
            "verification": status,
            "required_proofs": ",".join(sorted(needed)),
        })

    def all_proven(ids: frozenset[str]) -> bool:
        return bool(ids) and all(status_by_id.get(item) == "proven" for item in ids)

    return RequirementAudit(
        rows=tuple(rows),
        platform_ready=all_proven(PLATFORM_REQUIREMENTS),
        department_acceptance_ready=all_proven(DEPARTMENT_ACCEPTANCE_REQUIREMENTS),
    )
