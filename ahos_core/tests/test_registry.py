from __future__ import annotations

import pytest

from ahos import (
    ActionRequest,
    AuthorityLevel,
    Capability,
    Department,
    DepartmentCapabilityRegistry,
    GovernancePolicy,
)


def test_default_registry_covers_all_departments() -> None:
    registry = DepartmentCapabilityRegistry()

    assert set(registry.departments) == set(Department)
    assert all(registry.capabilities_for(department) for department in Department)


def test_registry_describes_capabilities_and_authority() -> None:
    registry = DepartmentCapabilityRegistry()

    assert registry.get("marketing.publish_campaign") == Capability(
        name="marketing.publish_campaign",
        department=Department.MARKETING,
        description="Publish a campaign to an external channel.",
        authority=AuthorityLevel.C,
    )
    assert registry.capabilities_for(Department.MARKETING) == (
        registry.get("marketing.publish_campaign"),
    )


def test_registry_is_local_and_inert() -> None:
    registry = DepartmentCapabilityRegistry()

    with pytest.raises(TypeError):
        registry.capabilities_by_department[Department.SOFTWARE] = ()
    with pytest.raises(AttributeError):
        registry.register(
            Capability("x", Department.SOFTWARE, "x", AuthorityLevel.B)
        )

    decision = GovernancePolicy().evaluate(
        ActionRequest(
            name="publish campaign",
            authority=registry.get("marketing.publish_campaign").authority,
        )
    )
    assert decision.allowed is False
    assert decision.owner_approval_required is True


def test_local_build_capability_remains_authority_b() -> None:
    registry = DepartmentCapabilityRegistry()
    capability = registry.get("software.build_and_test")

    assert capability.authority is AuthorityLevel.B
    decision = GovernancePolicy().evaluate(
        ActionRequest(name=capability.name, authority=capability.authority)
    )
    assert decision.allowed is True
    assert decision.owner_approval_required is False


def test_custom_registry_rejects_duplicate_names() -> None:
    capability = Capability(
        "software.example", Department.SOFTWARE, "Example.", AuthorityLevel.B
    )

    with pytest.raises(ValueError, match="duplicate capability"):
        DepartmentCapabilityRegistry((capability, capability))
