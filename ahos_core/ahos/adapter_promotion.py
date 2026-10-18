from __future__ import annotations

from dataclasses import dataclass

from .adapter_catalog import AdapterSpec, AdapterTrust


@dataclass(frozen=True, slots=True)
class AdapterPromotionEvidence:
    license_ok: bool
    security_scan_ok: bool
    sandbox_smoke_ok: bool
    deterministic_smoke_ok: bool
    terms_reviewed: bool
    version_pinned: bool
    maintenance_ok: bool
    network_scope_reviewed: bool


@dataclass(frozen=True, slots=True)
class AdapterPromotionDecision:
    promoted: bool
    target_trust: AdapterTrust
    blockers: tuple[str, ...]


class AdapterPromotionGate:
    CHECKS = (
        "license_ok",
        "security_scan_ok",
        "sandbox_smoke_ok",
        "deterministic_smoke_ok",
        "terms_reviewed",
        "version_pinned",
        "maintenance_ok",
        "network_scope_reviewed",
    )

    def evaluate(self, spec: AdapterSpec, evidence: AdapterPromotionEvidence) -> AdapterPromotionDecision:
        blockers = tuple(name for name in self.CHECKS if getattr(evidence, name) is not True)
        if not evidence.security_scan_ok:
            return AdapterPromotionDecision(False, AdapterTrust.BLOCKED, blockers)
        if blockers:
            return AdapterPromotionDecision(False, spec.trust, blockers)
        return AdapterPromotionDecision(True, AdapterTrust.REVIEWED_OPEN_SOURCE, ())
