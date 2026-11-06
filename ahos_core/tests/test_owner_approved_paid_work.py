from ahos.virtual_workforce import VirtualWorkforceRegistry, WorkerProfile, WorkerRole
from ahos.workforce_execution import VirtualWorkforceDispatcher, WorkItem, WorkStage


def test_paid_work_requires_owner_approval_but_can_run_after_explicit_approval():
    paid_worker = WorkerProfile(
        worker_id="paid-dev",
        name="Paid Dev",
        role=WorkerRole.SOFTWARE_ENGINEER,
        department="software",
        capabilities=frozenset({"python"}),
        daily_budget_usd=0.02,
        can_use_paid_ai=True,
    )
    registry = VirtualWorkforceRegistry((paid_worker,))
    dispatcher = VirtualWorkforceDispatcher(registry)

    blocked = dispatcher.assign(
        WorkItem(
            task_id="blocked",
            title="Paid task",
            department="software",
            required_capabilities=frozenset({"python"}),
            estimated_cost_usd=0.02,
        )
    )
    assert blocked.stage is WorkStage.BLOCKED
    assert blocked.owner_approval_required is True

    approved = dispatcher.assign(
        WorkItem(
            task_id="approved",
            title="Paid task",
            department="software",
            required_capabilities=frozenset({"python"}),
            estimated_cost_usd=0.02,
            owner_approved=True,
        )
    )
    assert approved.stage is WorkStage.ASSIGNED
    assert approved.worker_id == "paid-dev"