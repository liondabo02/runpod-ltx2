from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Iterable, Mapping

from .governance import AuthorityLevel


class Department(str, Enum):
    SOFTWARE = "software"
    MEDIA = "media"
    RESEARCH = "research"
    QA = "qa"
    COST = "cost"
    MARKETING = "marketing"
    CRM = "crm"
    ANALYTICS = "analytics"


def department_key(department: object) -> str:
    """Return the stable string id used for an AHOS department.

    Built-in departments are ``Department`` enum members; departments created
    later by the owner console are plain string ids. Both normalise to the same
    lowercase identifier so a single book can describe them.
    """

    value = getattr(department, "value", None)
    if isinstance(value, str):
        return value
    return str(department)


@dataclass(frozen=True, slots=True)
class Capability:
    name: str
    department: str
    description: str
    authority: AuthorityLevel


_DEFAULT_CAPABILITIES = (
    Capability(
        "software.inspect",
        Department.SOFTWARE,
        "Inspect local AHOS source and configuration.",
        AuthorityLevel.A,
    ),
    Capability(
        "software.build_and_test",
        Department.SOFTWARE,
        "Build and test reversible local AHOS changes.",
        AuthorityLevel.B,
    ),
    Capability(
        "media.create_draft",
        Department.MEDIA,
        "Prepare a local media draft without publishing it.",
        AuthorityLevel.B,
    ),
    Capability(
        "research.analyze",
        Department.RESEARCH,
        "Analyze locally available research material.",
        AuthorityLevel.A,
    ),
    Capability(
        "qa.run_tests",
        Department.QA,
        "Run local quality checks and report their results.",
        AuthorityLevel.B,
    ),
    Capability(
        "cost.observe",
        Department.COST,
        "Observe local cost metadata without changing budgets.",
        AuthorityLevel.A,
    ),
    Capability(
        "marketing.publish_campaign",
        Department.MARKETING,
        "Publish a campaign to an external channel.",
        AuthorityLevel.C,
    ),
    Capability(
        "crm.update_records",
        Department.CRM,
        "Update records in an external CRM system.",
        AuthorityLevel.C,
    ),
    Capability(
        "analytics.generate_report",
        Department.ANALYTICS,
        "Generate a local report from available metrics.",
        AuthorityLevel.A,
    ),
)


class DepartmentCapabilityRegistry:
    """Immutable local descriptions of departmental capabilities.

    The registry describes both the built-in ``Department`` members and any
    additional departments created at runtime (plain string ids). It remains
    immutable: extending it produces a new registry instead of mutating one.
    """

    def __init__(
        self,
        capabilities: Iterable[Capability] | None = None,
        *,
        extra_departments: Iterable[object] = (),
    ) -> None:
        entries = _DEFAULT_CAPABILITIES if capabilities is None else tuple(capabilities)

        order: dict[str, object] = {}
        if capabilities is None:
            # Preserve the historical contract: the default registry describes
            # every built-in department, in declaration order.
            for department in Department:
                order[department_key(department)] = department

        buckets: dict[str, list[Capability]] = {}
        by_name: dict[str, Capability] = {}

        for capability in entries:
            if capability.name in by_name:
                raise ValueError(f"duplicate capability {capability.name!r}")
            by_name[capability.name] = capability
            key = department_key(capability.department)
            buckets.setdefault(key, []).append(capability)
            order.setdefault(key, capability.department)

        for department in extra_departments:
            key = department_key(department)
            buckets.setdefault(key, [])
            order.setdefault(key, department)

        self._capabilities = MappingProxyType(by_name)
        self._order = MappingProxyType(order)
        self._capabilities_by_department = MappingProxyType(
            {
                order[key]: tuple(department_capabilities)
                for key, department_capabilities in buckets.items()
            }
        )

    @property
    def departments(self) -> tuple[object, ...]:
        return tuple(self._order.values())

    @property
    def capabilities_by_department(self) -> Mapping[object, tuple[Capability, ...]]:
        return self._capabilities_by_department

    def get(self, name: str) -> Capability | None:
        return self._capabilities.get(name)

    def capabilities_for(self, department: object) -> tuple[Capability, ...]:
        key = department_key(department)
        known = self._order.get(key)
        if known is None:
            raise KeyError(f"unknown department: {key!r}")
        return self._capabilities_by_department[known]


@dataclass(frozen=True)
class AgentLease:
    agent_id: str
    mission_id: str


class AgentRegistry:
    """Prevents the same logical agent from running two missions at once."""

    def __init__(self) -> None:
        self._leases: dict[str, AgentLease] = {}

    def acquire(self, agent_id: str, mission_id: str) -> AgentLease:
        if agent_id in self._leases:
            current = self._leases[agent_id]
            raise RuntimeError(
                f"agent {agent_id!r} already assigned to mission {current.mission_id!r}"
            )
        lease = AgentLease(agent_id=agent_id, mission_id=mission_id)
        self._leases[agent_id] = lease
        return lease

    def release(self, agent_id: str, mission_id: str) -> None:
        current = self._leases.get(agent_id)
        if current is None:
            return
        if current.mission_id != mission_id:
            raise RuntimeError("cannot release an agent lease owned by another mission")
        del self._leases[agent_id]

    def is_busy(self, agent_id: str) -> bool:
        return agent_id in self._leases
