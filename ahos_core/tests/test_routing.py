from __future__ import annotations

from ahos.governance import AuthorityLevel
from ahos.registry import Capability, Department, DepartmentCapabilityRegistry
from ahos.routing import DepartmentRoutingEngine, RoutingRequest


def _registry() -> DepartmentCapabilityRegistry:
    return DepartmentCapabilityRegistry(
        (
            Capability(
                "software.build_and_test",
                Department.SOFTWARE,
                "Build and test reversible local software changes.",
                AuthorityLevel.B,
            ),
            Capability(
                "analytics.generate_report",
                Department.ANALYTICS,
                "Generate an analytics report from metrics.",
                AuthorityLevel.A,
            ),
            Capability(
                "crm.update_records",
                Department.CRM,
                "Update records in an external CRM system.",
                AuthorityLevel.C,
            ),
        )
    )


def test_routes_objective_to_best_department_deterministically() -> None:
    engine = DepartmentRoutingEngine(_registry())

    decision = engine.route_mission(
        "m-1",
        "Build software and test the changes",
        max_authority=AuthorityLevel.B,
    )

    assert decision.primary is not None
    assert decision.primary.department is Department.SOFTWARE
    assert decision.primary.matched_capabilities == ("software.build_and_test",)
    assert "score=" in decision.primary.explanation


def test_exact_required_capability_has_strong_priority() -> None:
    engine = DepartmentRoutingEngine(_registry())

    decision = engine.route(
        RoutingRequest(
            mission_id="m-2",
            objective="Prepare something useful",
            required_capabilities=("analytics.generate_report",),
            max_authority=AuthorityLevel.B,
        )
    )

    assert decision.primary is not None
    assert decision.primary.department is Department.ANALYTICS
    assert decision.primary.score >= 100


def test_authority_ceiling_blocks_external_capabilities() -> None:
    engine = DepartmentRoutingEngine(_registry())

    decision = engine.route_mission(
        "m-3",
        "Update CRM records",
        required_capabilities=("crm.update_records",),
        max_authority=AuthorityLevel.B,
    )

    assert decision.blocked_capabilities == ("crm.update_records",)
    assert all(
        "crm.update_records" not in candidate.matched_capabilities
        for candidate in decision.candidates
    )


def test_unknown_required_capabilities_are_reported() -> None:
    engine = DepartmentRoutingEngine(_registry())

    decision = engine.route_mission(
        "m-4",
        "",
        required_capabilities=("unknown.capability",),
    )

    assert decision.primary is None
    assert decision.unmatched_required_capabilities == ("unknown.capability",)
