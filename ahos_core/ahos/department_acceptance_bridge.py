from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True, slots=True)
class DepartmentAcceptanceReport:
    passed: bool
    proofs: frozenset[str]
    blockers: tuple[str, ...]


class DepartmentAcceptanceBridge:
    """Consume existing department QA payloads without redefining their QA logic."""

    REQUIRED = {
        "studio_acceptance": ("studio", "accepted"),
        "identity_acceptance": ("identity", "accepted"),
        "language_acceptance": ("languages", "accepted"),
    }

    def evaluate(self, payloads: Mapping[str, Mapping[str, object]]) -> DepartmentAcceptanceReport:
        proofs: set[str] = set()
        blockers: list[str] = []
        for proof, (expected_kind, status_field) in self.REQUIRED.items():
            payload = payloads.get(proof)
            if not isinstance(payload, Mapping):
                blockers.append(f"{proof}:missing")
                continue
            if payload.get("kind") != expected_kind:
                blockers.append(f"{proof}:kind_mismatch")
                continue
            if payload.get(status_field) is not True:
                blockers.append(f"{proof}:not_accepted")
                continue
            if not str(payload.get("evidence_hash") or "").strip():
                blockers.append(f"{proof}:missing_evidence_hash")
                continue
            if payload.get("human_review_required") is True and payload.get("human_review_passed") is not True:
                blockers.append(f"{proof}:human_review_pending")
                continue
            proofs.add(proof)

        return DepartmentAcceptanceReport(
            passed=not blockers,
            proofs=frozenset(proofs),
            blockers=tuple(sorted(set(blockers))),
        )
