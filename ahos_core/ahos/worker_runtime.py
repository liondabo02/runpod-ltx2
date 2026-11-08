from __future__ import annotations

import time

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

    def _retry_with_alternative(
        self,
        item: WorkItem,
        failed: AssignmentDecision,
        failed_result: WorkerExecutionResult,
    ) -> tuple[AssignmentDecision, WorkerExecutionResult] | None:
        """One bounded retry on a *different* capable worker.

        The same worker is never retried, so a broken executor cannot loop.
        """

        candidates = [
            state
            for state in self.registry.matching_workers(
                item.required_capabilities, department=item.department
            )
            if state.profile.worker_id != failed.worker_id
            and state.profile.worker_id in self.executors
        ]
        if not candidates:
            return None

        try:
            from . import worker_metrics

            quality = worker_metrics.summary(worker_metrics.current_dir()) if worker_metrics.current_dir() else {}
        except Exception:  # pragma: no cover
            quality = {}
        candidates.sort(
            key=lambda state: -float(
                quality.get(state.profile.worker_id, {}).get("success_rate", 0.0)
            )
        )

        chosen = candidates[0]
        self.registry.assign(chosen.profile.worker_id, item.task_id)
        start = time.monotonic()
        result = self.executors[chosen.profile.worker_id](item, chosen.profile.worker_id)
        duration_ms = (time.monotonic() - start) * 1000.0

        if not result.success:
            # Basari yalnizca QA sonrasinda puanlanir; burada yalnizca
            # basarisiz deneme deftere yazilir.
            try:
                from . import worker_metrics

                worker_metrics.record_here(
                    worker_id=chosen.profile.worker_id,
                    mission_id=item.task_id,
                    step_id=item.task_id.rsplit(":", 1)[-1],
                    department=item.department,
                    success=False,
                    duration_ms=duration_ms,
                    reason=f"yeniden atama ({failed.worker_id} başarısız): {(result.summary or '')[:80]}",
                )
            except Exception:  # pragma: no cover
                pass
            self.registry.release(chosen.profile.worker_id, item.task_id)
            return None

        self.dispatcher.complete_worker_phase(item.task_id, chosen.profile.worker_id)
        return (
            AssignmentDecision(
                task_id=item.task_id,
                worker_id=chosen.profile.worker_id,
                stage=WorkStage.ASSIGNED,
                reason=f"yeniden atandı: {failed.worker_id} başarısız oldu",
            ),
            result,
        )

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

        start = time.monotonic()
        duration_ms = 0.0

        def record_outcome(*, passed: bool, reason: str) -> None:
            """Metrics reflect independent QA, not only the worker's own claim."""
            try:
                from . import worker_metrics

                worker_metrics.record_here(
                    worker_id=assignment.worker_id,
                    mission_id=item.task_id,
                    step_id=item.task_id.rsplit(":", 1)[-1],
                    department=item.department,
                    success=passed,
                    duration_ms=duration_ms,
                    reason=(reason or "")[:120],
                )
            except Exception:  # pragma: no cover - metrics must never break work
                pass

        try:
            worker_result = executor(item, assignment.worker_id)
        except Exception as exc:
            # Worker exceptions cannot strand an assigned worker indefinitely.
            duration_ms = (time.monotonic() - start) * 1000.0
            self.dispatcher.complete_worker_phase(item.task_id, assignment.worker_id)
            reason = f"worker executor raised {type(exc).__name__}"
            record_outcome(passed=False, reason=reason)
            return WorkforceRunResult(
                task_id=item.task_id,
                stage=WorkStage.BLOCKED,
                assignment=assignment,
                worker_result=None,
                qa_assignment=None,
                qa_result=None,
                reason=reason,
            )
        duration_ms = (time.monotonic() - start) * 1000.0
        self.dispatcher.complete_worker_phase(item.task_id, assignment.worker_id)

        if (worker_result.task_id != item.task_id
                or worker_result.worker_id != assignment.worker_id):
            reason = "worker result identity does not match assigned task"
            record_outcome(passed=False, reason=reason)
            return WorkforceRunResult(
                task_id=item.task_id,
                stage=WorkStage.BLOCKED,
                assignment=assignment,
                worker_result=worker_result,
                qa_assignment=None,
                qa_result=None,
                reason=reason,
            )

        if not worker_result.success:
            # Basarisiz deneme, alternatif isciye gecmeden ONCE kaydedilir;
            # aksi halde isci metrikleri gercek denemeleri saymaz.
            record_outcome(passed=False, reason=worker_result.summary)
            retry = self._retry_with_alternative(item, assignment, worker_result)
            if retry is not None:
                assignment, worker_result = retry
            if not worker_result.success:
                return WorkforceRunResult(
                    task_id=item.task_id,
                    stage=WorkStage.BLOCKED,
                    assignment=assignment,
                    worker_result=worker_result,
                    qa_assignment=None,
                    qa_result=None,
                    reason=(
                        "executor_unavailable: Üretim yürütücüsü bağlı değil; sonraki adım: uygun yürütücüyü bağla ve kabul testi çalıştır"
                        if "Üretim yürütücüsü bağlı değil" in (worker_result.summary or "")
                        else (worker_result.summary or "worker execution failed")
                    ),
                )

        qa_assignment = self.dispatcher.assign_qa(item.task_id, producer_id=assignment.worker_id)
        if qa_assignment.stage is WorkStage.BLOCKED or not qa_assignment.qa_worker_id:
            record_outcome(passed=False, reason=qa_assignment.reason)
            return WorkforceRunResult(
                task_id=item.task_id,
                stage=WorkStage.BLOCKED,
                assignment=assignment,
                worker_result=worker_result,
                qa_assignment=qa_assignment,
                qa_result=None,
                reason=qa_assignment.reason,
            )

        try:
            qa_result = self.qa_executor(
                item,
                worker_result,
                qa_assignment.qa_worker_id,
            )
        except Exception as exc:
            # The QA lease must be released even if the verifier crashes.
            self.dispatcher.complete_qa(
                item.task_id, qa_assignment.qa_worker_id, passed=False,
            )
            reason = f"QA executor raised {type(exc).__name__}"
            record_outcome(passed=False, reason=reason)
            return WorkforceRunResult(
                task_id=item.task_id,
                stage=WorkStage.BLOCKED,
                assignment=assignment,
                worker_result=worker_result,
                qa_assignment=qa_assignment,
                qa_result=QaExecutionResult(
                    task_id=item.task_id,
                    qa_worker_id=qa_assignment.qa_worker_id,
                    passed=False,
                    summary=reason,
                ),
                reason=reason,
            )
        identity_ok = (
            qa_result.task_id == item.task_id
            and qa_result.qa_worker_id == qa_assignment.qa_worker_id
        )
        verified = bool(qa_result.passed and identity_ok)
        final = self.dispatcher.complete_qa(
            item.task_id,
            qa_assignment.qa_worker_id,
            passed=verified,
        )
        reason = (
            "QA result identity does not match assigned task or verifier"
            if not identity_ok
            else final.reason if verified else f"QA failed: {qa_result.summary}"
        )
        record_outcome(
            passed=verified and final.stage is WorkStage.COMPLETED,
            reason=reason,
        )

        return WorkforceRunResult(
            task_id=item.task_id,
            stage=final.stage,
            assignment=assignment,
            worker_result=worker_result,
            qa_assignment=qa_assignment,
            qa_result=qa_result,
            reason=reason,
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
