from __future__ import annotations

from ahos import worker_metrics
from ahos.virtual_workforce import (
    VirtualWorkforceRegistry,
    WorkerProfile,
    WorkerRole,
)
from ahos.worker_runtime import (
    VirtualWorkerRuntime,
    WorkItem,
    WorkerExecutionResult,
)


def _profile(worker_id: str) -> WorkerProfile:
    return WorkerProfile(
        worker_id=worker_id,
        name=worker_id,
        role=WorkerRole.SOFTWARE_ENGINEER,
        department="oyun",
        capabilities=frozenset({"code"}),
    )


def _item() -> WorkItem:
    return WorkItem(
        task_id="m-1:produce",
        title="kod",
        department="oyun",
        required_capabilities=frozenset({"code"}),
    )


def test_failed_worker_is_replaced_by_alternative(tmp_path) -> None:
    worker_metrics.configure(tmp_path)
    registry = VirtualWorkforceRegistry()
    registry.register(_profile("engineer-a"))
    registry.register(_profile("engineer-b"))

    calls: list[str] = []

    def failing(item, worker_id):
        calls.append(worker_id)
        return WorkerExecutionResult(
            task_id=item.task_id,
            worker_id=worker_id,
            success=False,
            summary="dosya yazılamadı",
            artifacts=(),
        )

    def working(item, worker_id):
        calls.append(worker_id)
        return WorkerExecutionResult(
            task_id=item.task_id,
            worker_id=worker_id,
            success=True,
            summary="tamam",
            artifacts=(),
        )

    runtime = VirtualWorkerRuntime(
        registry,
        {"engineer-a": failing, "engineer-b": working},
        qa_executor=lambda item, result, qa: __import__(
            "ahos.worker_runtime", fromlist=["QaExecutionResult"]
        ).QaExecutionResult(
            task_id=item.task_id, qa_worker_id=qa, passed=True, summary="ok"
        ),
    )
    registry.register(
        WorkerProfile(
            worker_id="qa-1",
            name="qa",
            role=WorkerRole.QA_ENGINEER,
            department="quality",
            capabilities=frozenset({"qa"}),
        )
    )

    outcome = runtime.run(_item())

    assert outcome.stage.value in {"completed", "ready_for_qa"}
    assert outcome.worker_result is not None and outcome.worker_result.success is True
    assert calls == ["engineer-a", "engineer-b"], calls
    metrics = worker_metrics.summary(tmp_path)
    assert metrics["engineer-a"]["failures"] == 1
    assert metrics["engineer-b"]["successes"] == 1


def test_same_worker_is_not_retried(tmp_path) -> None:
    worker_metrics.configure(tmp_path)
    registry = VirtualWorkforceRegistry()
    registry.register(_profile("engineer-a"))

    calls: list[str] = []

    def failing(item, worker_id):
        calls.append(worker_id)
        return WorkerExecutionResult(
            task_id=item.task_id,
            worker_id=worker_id,
            success=False,
            summary="hata",
            artifacts=(),
        )

    runtime = VirtualWorkerRuntime(
        registry,
        {"engineer-a": failing},
        qa_executor=lambda item, result, qa: None,
    )

    outcome = runtime.run(_item())

    # Hata nedeni artık gerçek özetten geliyor (tanı için şart).\n    assert outcome.reason == "hata"
    assert calls == ["engineer-a"]
