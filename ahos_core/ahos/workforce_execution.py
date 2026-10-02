from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .virtual_workforce import (
    VirtualWorkforceRegistry,
    WorkerRuntimeState,
    WorkerRole,
)


class WorkStage(str, Enum):
    PLANNED = "planned"
    ASSIGNED = "assigned"
    READY_FOR_QA = "ready_for_qa"
    COMPLETED = "completed"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class WorkItem:
    task_id: str
    title: str
    department: str
    required_capabilities: frozenset[str]
    estimated_cost_usd: float = 0.0
    external_side_effect: bool = False
    destructive: bool = False
    touches_secrets: bool = False
    requires_owner_approval: bool = False
    owner_approved: bool = False

    def __post_init__(self) -> None:
        if not self.task_id.strip():
            raise ValueError("task_id must not be empty")
        if not self.title.strip():
            raise ValueError("title must not be empty")
        if not self.department.strip():
            raise ValueError("department must not be empty")
        if self.estimated_cost_usd < 0:
            raise ValueError("estimated_cost_usd must be >= 0")


@dataclass(frozen=True, slots=True)
class AssignmentDecision:
    task_id: str
    worker_id: str | None
    stage: WorkStage
    reason: str
    owner_approval_required: bool = False


@dataclass(frozen=True, slots=True)
class QaDecision:
    task_id: str
    qa_worker_id: str | None
    stage: WorkStage
    reason: str


class VirtualWorkforceDispatcher:
    """Local task router for AHOS virtual employees.

    This layer performs only deterministic assignment/lifecycle control.
    It does not call an LLM, access the network, or perform external actions.
    """

    def __init__(self, registry: VirtualWorkforceRegistry) -> None:
        self.registry = registry

    @staticmethod
    def _approval_required(item: WorkItem) -> bool:
        protected_action = any(
            (
                item.requires_owner_approval,
                item.external_side_effect,
                item.destructive,
                item.touches_secrets,
                item.estimated_cost_usd > 0,
            )
        )
        return protected_action and not item.owner_approved

    def assign(self, item: WorkItem) -> AssignmentDecision:
        if self._approval_required(item):
            return AssignmentDecision(
                task_id=item.task_id,
                worker_id=None,
                stage=WorkStage.BLOCKED,
                reason="owner approval required before execution",
                owner_approval_required=True,
            )

        matches = self.registry.matching_workers(
            item.required_capabilities,
            department=item.department,
            estimated_cost_usd=item.estimated_cost_usd,
        )
        if not matches:
            return AssignmentDecision(
                task_id=item.task_id,
                worker_id=None,
                stage=WorkStage.BLOCKED,
                reason="no available worker matches department/capabilities/budget",
            )

        worker = matches[0]
        self.registry.assign(
            worker.profile.worker_id,
            item.task_id,
            estimated_cost_usd=item.estimated_cost_usd,
        )
        return AssignmentDecision(
            task_id=item.task_id,
            worker_id=worker.profile.worker_id,
            stage=WorkStage.ASSIGNED,
            reason="best available matching worker assigned",
        )

    def complete_worker_phase(
        self,
        task_id: str,
        worker_id: str,
    ) -> AssignmentDecision:
        self.registry.release(worker_id, task_id)
        return AssignmentDecision(
            task_id=task_id,
            worker_id=worker_id,
            stage=WorkStage.READY_FOR_QA,
            reason="worker phase complete; QA required",
        )

    def assign_qa(self, task_id: str) -> QaDecision:
        matches = self.registry.matching_workers({"qa"}, department="quality")
        if not matches:
            matches = self.registry.matching_workers({"verification"}, department="quality")

        if not matches:
            return QaDecision(
                task_id=task_id,
                qa_worker_id=None,
                stage=WorkStage.BLOCKED,
                reason="no QA worker available",
            )

        qa = matches[0]
        self.registry.assign(qa.profile.worker_id, task_id)
        return QaDecision(
            task_id=task_id,
            qa_worker_id=qa.profile.worker_id,
            stage=WorkStage.ASSIGNED,
            reason="QA worker assigned",
        )

    def complete_qa(
        self,
        task_id: str,
        qa_worker_id: str,
        *,
        passed: bool,
    ) -> QaDecision:
        self.registry.release(qa_worker_id, task_id)
        return QaDecision(
            task_id=task_id,
            qa_worker_id=qa_worker_id,
            stage=WorkStage.COMPLETED if passed else WorkStage.BLOCKED,
            reason="QA passed" if passed else "QA failed; return to work queue",
        )


def manager_for_department(
    workers: Iterable[WorkerRuntimeState],
    department: str,
) -> WorkerRuntimeState | None:
    managers = [
        state
        for state in workers
        if state.profile.department == department
        and state.profile.role is WorkerRole.DEPARTMENT_MANAGER
    ]
    managers.sort(key=lambda state: state.profile.worker_id)
    return managers[0] if managers else None
