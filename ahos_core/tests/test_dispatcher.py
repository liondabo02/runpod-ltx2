from __future__ import annotations

from ahos.dispatcher import DispatchState, MissionDispatcher
from ahos.governance import AuthorityLevel
from ahos.registry import Capability, Department, DepartmentCapabilityRegistry
from ahos.routing import DepartmentRoutingEngine


def _dispatcher() -> MissionDispatcher:
    registry = DepartmentCapabilityRegistry(
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
                "Generate a local analytics report.",
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
    return MissionDispatcher(DepartmentRoutingEngine(registry))


def test_ready_envelope_combines_routing_retry_and_audit_metadata() -> None:
    envelope = _dispatcher().build_envelope(
        "m-10",
        "Build and test software changes",
        required_capabilities=("software.build_and_test",),
        audit_correlation_id="mission:m-10:dispatch-1",
        max_attempts=3,
    )

    assert envelope.dispatchable is True
    assert envelope.dispatch_state is DispatchState.READY
    assert envelope.routing.primary is not None
    assert envelope.routing.primary.department is Department.SOFTWARE
    assert envelope.retry_policy.max_attempts == 3
    assert envelope.audit.correlation_id == "mission:m-10:dispatch-1"


def test_dependencies_block_dispatch() -> None:
    envelope = _dispatcher().build_envelope(
        "m-11",
        "Build and test software changes",
        dependency_ready=False,
        required_capabilities=("software.build_and_test",),
    )

    assert envelope.dispatch_state is DispatchState.BLOCKED
    assert "dependencies" in envelope.reasons[0]


def test_owner_approval_requirement_blocks_until_approved() -> None:
    dispatcher = _dispatcher()

    waiting = dispatcher.build_envelope(
        "m-12",
        "Generate analytics report",
        required_capabilities=("analytics.generate_report",),
        owner_approval_required=True,
        approval_status="pending",
    )
    approved = dispatcher.build_envelope(
        "m-12",
        "Generate analytics report",
        required_capabilities=("analytics.generate_report",),
        owner_approval_required=True,
        approval_status="approved",
    )

    assert waiting.dispatch_state is DispatchState.WAITING_APPROVAL
    assert approved.dispatch_state is DispatchState.READY


def test_authority_block_from_router_is_preserved() -> None:
    envelope = _dispatcher().build_envelope(
        "m-13",
        "Update CRM records",
        required_capabilities=("crm.update_records",),
        max_authority=AuthorityLevel.B,
    )

    assert envelope.dispatch_state is DispatchState.BLOCKED
    assert envelope.routing.blocked_capabilities == ("crm.update_records",)


def test_failed_execution_becomes_retryable_until_budget_exhausted() -> None:
    dispatcher = _dispatcher()

    retryable = dispatcher.build_envelope(
        "m-14",
        "Build and test software changes",
        required_capabilities=("software.build_and_test",),
        execution_result_state="failed",
        attempt=1,
        max_attempts=2,
    )
    exhausted = dispatcher.build_envelope(
        "m-14",
        "Build and test software changes",
        required_capabilities=("software.build_and_test",),
        execution_result_state="failed",
        attempt=2,
        max_attempts=2,
    )

    assert retryable.dispatch_state is DispatchState.RETRYABLE
    assert exhausted.dispatch_state is DispatchState.FAILED
