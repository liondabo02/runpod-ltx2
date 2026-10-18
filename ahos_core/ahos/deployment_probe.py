from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True, slots=True)
class DeploymentProbeReport:
    passed: bool
    blockers: tuple[str, ...]


class DeploymentProbe:
    REQUIRED_FIELDS = frozenset({
        "commit_sha",
        "artifact_sha256",
        "environment",
        "deployed_at",
        "healthcheck_passed",
        "rollback_ready",
        "secrets_externalized",
    })

    def evaluate(self, receipt: Mapping[str, object]) -> DeploymentProbeReport:
        blockers: list[str] = []
        missing = self.REQUIRED_FIELDS - set(receipt)
        blockers.extend(f"missing:{name}" for name in sorted(missing))
        if missing:
            return DeploymentProbeReport(False, tuple(blockers))

        if not str(receipt.get("commit_sha") or "").strip():
            blockers.append("invalid_commit_sha")
        digest = str(receipt.get("artifact_sha256") or "")
        if len(digest) != 64 or any(char not in "0123456789abcdefABCDEF" for char in digest):
            blockers.append("invalid_artifact_sha256")
        if not str(receipt.get("environment") or "").strip():
            blockers.append("invalid_environment")
        if receipt.get("healthcheck_passed") is not True:
            blockers.append("healthcheck_not_passed")
        if receipt.get("rollback_ready") is not True:
            blockers.append("rollback_not_ready")
        if receipt.get("secrets_externalized") is not True:
            blockers.append("secrets_not_externalized")
        if receipt.get("live_owner_approved") is True and receipt.get("environment") != "production":
            blockers.append("owner_approval_environment_mismatch")

        return DeploymentProbeReport(
            passed=not blockers,
            blockers=tuple(sorted(set(blockers))),
        )
