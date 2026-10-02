from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class OwnerPolicy:
    allow_external_spend: bool = False
    allow_publish: bool = False
    allow_destructive: bool = False
    allow_secret_changes: bool = False

    def evaluate(self, task: str) -> PolicyDecision:
        text = task.lower()
        reasons: list[str] = []

        if not self.allow_external_spend and any(
            word in text for word in ("runpod", "gpu", "billing", "payment", "purchase", "spend", "buy")
        ):
            reasons.append("external spend requires owner approval")
        if not self.allow_publish and any(
            phrase in text for phrase in ("publish", "post publicly", "upload to youtube", "release production")
        ):
            reasons.append("external publishing requires owner approval")
        if not self.allow_destructive and any(
            phrase in text for phrase in ("delete", "destroy", "drop database", "remove volume", "force push")
        ):
            reasons.append("destructive action requires owner approval")
        if not self.allow_secret_changes and any(
            phrase in text for phrase in ("api key", "secret", "credential", "token")
        ):
            reasons.append("credential changes require owner approval")

        return PolicyDecision(allowed=not reasons, reasons=tuple(reasons))
