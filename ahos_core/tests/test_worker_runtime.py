from __future__ import annotations

from ahos.virtual_workforce import VirtualWorkforceRegistry, default_virtual_workforce
from ahos.worker_runtime import (
    QaExecutionResult,
    VirtualWorkerRuntime,
    WorkerExecutionResult,
    local_pass_qa,
    make_local_text_executor,
)
from ahos.workforce_execution import WorkItem, WorkStage


def _software_item(task_id: str = "task-1") -> WorkItem:
    return WorkItem(
        task_id=task_id,
        title="Build Python API automation",
        department="software",
        required_capabilities=frozenset({"python", "api", "automation"}),
    )


def test_real_runtime_worker_to_qa_to_completed() -> None:
    registry = VirtualWorkforceRegistry(default_virtual_workforce())
    runtime = VirtualWorkerRuntime(
        registry,
        executors={
            "dev-01": make_local_text_executor(
                lambda item, worker_id: f"{worker_id} completed {item.title}"
            )
        },
        qa_executor=local_pass_qa,
    )

    result = runtime.run(_software_item())

    assert result.stage is WorkStage.COMPLETED
    assert result.worker_result is not None
    assert result.worker_result.worker_id == "dev-01"
    assert result.qa_result is not None
    assert result.qa_result.qa_worker_id == "qa-01"
    assert registry.get("dev-01").is_available is True
    assert registry.get("qa-01").is_available is True


def test_missing_worker_executor_blocks_safely_and_releases_worker() -> None:
    registry = VirtualWorkforceRegistry(default_virtual_workforce())
    runtime = VirtualWorkerRuntime(
        registry,
        executors={},
        qa_executor=local_pass_qa,
    )

    result = runtime.run(_software_item())

    assert result.stage is WorkStage.BLOCKED
    assert "no executor registered" in result.reason
    assert registry.get("dev-01").is_available is True


def test_worker_failure_never_reaches_qa() -> None:
    registry = VirtualWorkforceRegistry(default_virtual_workforce())

    def fail(item: WorkItem, worker_id: str) -> WorkerExecutionResult:
        return WorkerExecutionResult(
            task_id=item.task_id,
            worker_id=worker_id,
            success=False,
            summary="execution failed",
        )

    runtime = VirtualWorkerRuntime(
        registry,
        executors={"dev-01": fail},
        qa_executor=local_pass_qa,
    )

    result = runtime.run(_software_item())

    assert result.stage is WorkStage.BLOCKED
    assert result.qa_assignment is None
    assert result.qa_result is None


def test_qa_failure_blocks_completion() -> None:
    registry = VirtualWorkforceRegistry(default_virtual_workforce())

    def reject_qa(
        item: WorkItem,
        worker_result: WorkerExecutionResult,
        qa_worker_id: str,
    ) -> QaExecutionResult:
        return QaExecutionResult(
            task_id=item.task_id,
            qa_worker_id=qa_worker_id,
            passed=False,
            summary="verification failed",
        )

    runtime = VirtualWorkerRuntime(
        registry,
        executors={
            "dev-01": make_local_text_executor(
                lambda item, worker_id: "worker produced result"
            )
        },
        qa_executor=reject_qa,
    )

    result = runtime.run(_software_item())

    assert result.stage is WorkStage.BLOCKED
    assert result.qa_result is not None
    assert result.qa_result.passed is False


def test_paid_or_external_work_remains_blocked_before_executor() -> None:
    registry = VirtualWorkforceRegistry(default_virtual_workforce())
    calls: list[str] = []

    def executor(item: WorkItem, worker_id: str) -> WorkerExecutionResult:
        calls.append(item.task_id)
        return WorkerExecutionResult(
            task_id=item.task_id,
            worker_id=worker_id,
            success=True,
            summary="should not run",
        )

    runtime = VirtualWorkerRuntime(
        registry,
        executors={"dev-01": executor},
        qa_executor=local_pass_qa,
    )

    paid = WorkItem(
        task_id="paid",
        title="Paid AI task",
        department="software",
        required_capabilities=frozenset({"python"}),
        estimated_cost_usd=0.01,
    )
    external = WorkItem(
        task_id="external",
        title="External action",
        department="software",
        required_capabilities=frozenset({"python"}),
        external_side_effect=True,
    )

    assert runtime.run(paid).stage is WorkStage.BLOCKED
    assert runtime.run(external).stage is WorkStage.BLOCKED
    assert calls == []
