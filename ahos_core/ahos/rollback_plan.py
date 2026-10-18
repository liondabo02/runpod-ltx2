from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RollbackPlan:
    from_version: str
    to_version: str
    artifact_sha256: str
    healthcheck: str
    requires_owner_approval: bool = True


class RollbackPlanner:
    def build(self, *, current_version: str, previous_version: str, artifact_sha256: str, healthcheck: str) -> RollbackPlan:
        if not current_version or not previous_version:
            raise ValueError("versions are required")
        if current_version == previous_version:
            raise ValueError("rollback target must differ")
        if len(artifact_sha256) != 64:
            raise ValueError("artifact sha256 required")
        if not healthcheck:
            raise ValueError("healthcheck required")
        return RollbackPlan(current_version, previous_version, artifact_sha256, healthcheck, True)
