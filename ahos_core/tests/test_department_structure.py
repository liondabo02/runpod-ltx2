from ahos.department_structure import (
    CORE_DEPARTMENTS,
    build_department_structure,
)
from ahos.virtual_workforce import (
    VirtualWorkforceRegistry,
    WorkerRole,
    default_virtual_workforce,
)
from ahos.workforce_execution import manager_for_department


def test_every_core_department_has_exactly_one_manager_and_specialist():
    workforce = default_virtual_workforce()
    structure = build_department_structure(workforce)

    assert tuple(item.department for item in structure) == CORE_DEPARTMENTS
    assert len(structure) == 11
    assert all(item.manager_id.startswith("mgr-") for item in structure)
    assert all(item.worker_ids for item in structure)


def test_all_department_managers_are_routable():
    registry = VirtualWorkforceRegistry(default_virtual_workforce())

    for department in CORE_DEPARTMENTS:
        manager = manager_for_department(registry.all(), department)
        assert manager is not None
        assert manager.profile.role is WorkerRole.DEPARTMENT_MANAGER
        assert manager.profile.department == department


def test_expanded_workforce_keeps_specialist_routing_stable():
    registry = VirtualWorkforceRegistry(default_virtual_workforce())

    cases = (
        ("research", {"research"}, "research-01"),
        ("software", {"python", "automation"}, "dev-01"),
        ("quality", {"qa"}, "qa-01"),
        ("infrastructure", {"devops"}, "devops-01"),
        ("data", {"analytics"}, "data-01"),
        ("creative", {"design"}, "design-01"),
        ("marketing", {"marketing"}, "marketing-01"),
        ("sales", {"sales"}, "sales-01"),
        ("finance", {"finance"}, "finance-01"),
        ("operations", {"operations"}, "ops-01"),
        ("support", {"support"}, "support-01"),
    )

    for department, capabilities, worker_id in cases:
        matches = registry.matching_workers(
            capabilities,
            department=department,
        )
        assert matches
        assert matches[0].profile.worker_id == worker_id


def test_expanded_workforce_is_zero_cost_by_default():
    workforce = default_virtual_workforce()

    assert len(workforce) >= 22
    assert all(profile.can_use_paid_ai is False for profile in workforce)
    assert all(profile.daily_budget_usd == 0.0 for profile in workforce)
