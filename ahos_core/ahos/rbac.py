from __future__ import annotations

from dataclasses import dataclass


DEFAULT_ROLES: dict[str, frozenset[str]] = {
    "viewer": frozenset({"read"}),
    "worker": frozenset({"read", "draft", "test"}),
    "maintainer": frozenset({"read", "draft", "test", "commit_branch"}),
    "owner": frozenset({"read", "draft", "test", "commit_branch", "approve_external", "approve_privileged"}),
}


@dataclass(frozen=True, slots=True)
class AccessDecision:
    allowed: bool
    reason: str


class RBACPolicy:
    def __init__(self, roles: dict[str, frozenset[str]] | None = None) -> None:
        self.roles = roles or DEFAULT_ROLES

    def check(self, role: str, permission: str) -> AccessDecision:
        permissions = self.roles.get(role)
        if permissions is None:
            return AccessDecision(False, "unknown_role")
        if permission not in permissions:
            return AccessDecision(False, "permission_denied")
        return AccessDecision(True, "allowed")
