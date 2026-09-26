from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Protocol

from .virtual_workforce import VirtualWorkforceRegistry
from .workforce_execution import (
    AssignmentDecision,
    QaDecision,
    VirtualWorkforceDispatcher,
    WorkItem,
    WorkStage,
)


@dataclass(frozen=True, slots=True)
class WorkerExecutionResult:
    task_id: str
    worker_id: str
    success: bool
    summary: str
    artifacts: tuple[str, ...] = ()
    tests_run: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class QaExecutionResult:
    task_id: str
    qa_worker_id: str
    passed: bool
    summary: str


@dataclass(frozen=True, slots=True)
class WorkforceRunResult:
    task_id: str
    stage: WorkStage
    assignment: AssignmentDecision
    worker_result: WorkerExecutionResult | None
    qa_assignment: QaDecision | None
    qa_result: QaExecutionResult | None
    reason: str


class WorkerExecutor(Protocol):
    def __call__(self, item: WorkItem, worker_id: str) -> WorkerExecutionResult: ...


class QaExecutor(Protocol):
    def __call__(
        self,
        item: WorkItem,
        worker_result: WorkerExecutionResult,
        qa_worker_id: str,
    ) -> QaExecutionResult: ...


class VirtualWorkerRuntime:
    """Executes a local AHOS work item through worker -> QA lifecycle.

    Executors are injected. This keeps the orchestration layer independent from
    any specific LLM, browser, shell, or external service. No paid AI or network
    access happens unless an injected executor explicitly performs it.
    """

    def __init__(
        self,
        registry: VirtualWorkforceRegistry,
        executors: Mapping[str, WorkerExecutor],
        qa_executor: QaExecutor,
    ) -> None:
        self.registry = registry
        self.dispatcher = VirtualWorkforceDispatcher(registry)
        self.executors = dict(executors)
        self.qa_executor = qa_executor

    def run(self, item: WorkItem) -> WorkforceRunResult:
        assignment = self.dispatcher.assign(item)
        if assignment.stage is WorkStage.BLOCKED or not assignment.worker_id:
            return WorkforceRunResult(
                task_id=item.task_id,
                stage=WorkStage.BLOCKED,
                assignment=assignment,
                worker_result=None,
                qa_assignment=None,
                qa_result=None,
                reason=assignment.reason,
            )

        executor = self.executors.get(assignment.worker_id)
        if executor is None:
            self.registry.release(assignment.worker_id, item.task_id)
            return WorkforceRunResult(
                task_id=item.task_id,
                stage=WorkStage.BLOCKED,
                assignment=assignment,
                worker_result=None,
                qa_assignment=None,
                qa_result=None,
                reason=f"no executor registered for worker {assignment.worker_id}",
            )

        worker_result = executor(item, assignment.worker_id)
        self.dispatcher.complete_worker_phase(item.task_id, assignment.worker_id)

        if not worker_result.success:
            return WorkforceRunResult(
                task_id=item.task_id,
                stage=WorkStage.BLOCKED,
                assignment=assignment,
                worker_result=worker_result,
                qa_assignment=None,
                qa_result=None,
                reason="worker execution failed",
            )

        qa_assignment = self.dispatcher.assign_qa(item.task_id)
        if qa_assignment.stage is WorkStage.BLOCKED or not qa_assignment.qa_worker_id:
            return WorkforceRunResult(
                task_id=item.task_id,
                stage=WorkStage.BLOCKED,
                assignment=assignment,
                worker_result=worker_result,
                qa_assignment=qa_assignment,
                qa_result=None,
                reason=qa_assignment.reason,
            )

        qa_result = self.qa_executor(
            item,
            worker_result,
            qa_assignment.qa_worker_id,
        )
        final = self.dispatcher.complete_qa(
            item.task_id,
            qa_assignment.qa_worker_id,
            passed=qa_result.passed,
        )

        return WorkforceRunResult(
            task_id=item.task_id,
            stage=final.stage,
            assignment=assignment,
            worker_result=worker_result,
            qa_assignment=qa_assignment,
            qa_result=qa_result,
            reason=final.reason,
        )


def make_local_text_executor(
    summary_builder: Callable[[WorkItem, str], str],
) -> WorkerExecutor:
    """Create a deterministic zero-cost local executor for tests/bootstrap."""

    def _execute(item: WorkItem, worker_id: str) -> WorkerExecutionResult:
        return WorkerExecutionResult(
            task_id=item.task_id,
            worker_id=worker_id,
            success=True,
            summary=summary_builder(item, worker_id),
        )

    return _execute


def local_pass_qa(
    item: WorkItem,
    worker_result: WorkerExecutionResult,
    qa_worker_id: str,
) -> QaExecutionResult:
    """Bootstrap QA executor used only for deterministic local verification."""
    passed = worker_result.success and bool(worker_result.summary.strip())
    return QaExecutionResult(
        task_id=item.task_id,
        qa_worker_id=qa_worker_id,
        passed=passed,
        summary="local deterministic QA passed" if passed else "local deterministic QA failed",
    )
