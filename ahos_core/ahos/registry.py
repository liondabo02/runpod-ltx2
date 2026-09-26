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


@dataclass(frozen=True, slots=True)
class Capability:
    name: str
    department: Department
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
    """Immutable local descriptions of departmental capabilities."""

    def __init__(self, capabilities: Iterable[Capability] | None = None) -> None:
        entries = _DEFAULT_CAPABILITIES if capabilities is None else tuple(capabilities)
        by_name: dict[str, Capability] = {}
        by_department: dict[Department, list[Capability]] = {
            department: [] for department in Department
        }
        for capability in entries:
            if capability.name in by_name:
                raise ValueError(f"duplicate capability {capability.name!r}")
            by_name[capability.name] = capability
            by_department[capability.department].append(capability)

        self._capabilities = MappingProxyType(by_name)
        self._capabilities_by_department = MappingProxyType(
            {
                department: tuple(department_capabilities)
                for department, department_capabilities in by_department.items()
            }
        )

    @property
    def departments(self) -> tuple[Department, ...]:
        return tuple(Department)

    @property
    def capabilities_by_department(self) -> Mapping[Department, tuple[Capability, ...]]:
        return self._capabilities_by_department

    def get(self, name: str) -> Capability | None:
        return self._capabilities.get(name)

    def capabilities_for(self, department: Department) -> tuple[Capability, ...]:
        return self._capabilities_by_department[Department(department)]


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
