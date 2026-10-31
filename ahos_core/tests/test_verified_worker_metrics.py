"""Worker quality score must follow independent QA, not claimed worker success."""

from __future__ import annotations

from ahos import worker_metrics
from ahos.virtual_workforce import VirtualWorkforceRegistry, default_virtual_workforce
from ahos.worker_runtime import (
    QaExecutionResult,
    VirtualWorkerRuntime,
    make_local_text_executor,
)
from ahos.workforce_execution import WorkItem, WorkStage


def _item(name: str) -> WorkItem:
    return WorkItem(
        task_id=f"qa-metric:{name}",
        title="Do work then verify",
        department="software",
        required_capabilities=frozenset({"python", "api", "automation"}),
    )


def _execute(tmp_path, *, qa_passed: bool, label: str):
    registry = VirtualWorkforceRegistry(default_virtual_workforce())

    def independent_qa(item, worker_result, verifier):
        assert verifier != worker_result.worker_id
        return QaExecutionResult(
            task_id=item.task_id, qa_worker_id=verifier,
            passed=qa_passed, summary="verified" if qa_passed else "failed acceptance",
        )

    worker_metrics.configure(tmp_path)
    try:
        runtime = VirtualWorkerRuntime(
            registry,
            executors={"dev-01": make_local_text_executor(
                lambda item, worker_id: "I finished"  # claim alone is not QA
            )},
            qa_executor=independent_qa,
        )
        outcome = runtime.run(_item(label))
        stats = worker_metrics.summary(tmp_path).get("dev-01")
        return outcome, stats
    finally:
        worker_metrics.configure(None)


def test_failed_qa_cannot_inflate_worker_success_rate(tmp_path):
    outcome, stats = _execute(tmp_path, qa_passed=False, label="rejected")
    assert outcome.stage is WorkStage.BLOCKED
    assert stats["runs"] == 1
    assert stats["successes"] == 0
    assert stats["failures"] == 1
    assert "QA failed" in stats["last_error"]


def test_worker_success_after_independent_qa_is_counted(tmp_path):
    outcome, stats = _execute(tmp_path, qa_passed=True, label="accepted")
    assert outcome.stage is WorkStage.COMPLETED
    assert stats["runs"] == 1
    assert stats["successes"] == 1
    assert stats["failures"] == 0


def test_qa_blocked_cannot_count_worker_as_success(tmp_path):
    registry = VirtualWorkforceRegistry(default_virtual_workforce())
    registry.pause("qa-01")
    worker_metrics.configure(tmp_path)
    try:
        runtime = VirtualWorkerRuntime(
            registry,
            executors={"dev-01": make_local_text_executor(lambda item, worker: "done")},
            qa_executor=lambda *args: (_ for _ in ()).throw(AssertionError("QA must not run")),
        )
        outcome = runtime.run(_item("no-verifier"))
        assert outcome.stage is WorkStage.BLOCKED
        assert worker_metrics.summary(tmp_path)["dev-01"]["successes"] == 0
    finally:
        worker_metrics.configure(None)


def test_worker_crash_releases_lease_and_counts_failure(tmp_path):
    registry = VirtualWorkforceRegistry(default_virtual_workforce())
    worker_metrics.configure(tmp_path)
    try:
        def crash(item, worker_id):
            raise RuntimeError("not a completed job")

        runtime = VirtualWorkerRuntime(
            registry,
            executors={"dev-01": crash},
            qa_executor=lambda *args: (_ for _ in ()).throw(AssertionError("QA must not run")),
        )
        outcome = runtime.run(_item("worker-crash"))
        assert outcome.stage is WorkStage.BLOCKED
        assert "RuntimeError" in outcome.reason
        assert registry.get("dev-01").is_available
        assert worker_metrics.summary(tmp_path)["dev-01"]["failures"] == 1
    finally:
        worker_metrics.configure(None)


def test_qa_crash_releases_verifier_and_counts_failure(tmp_path):
    registry = VirtualWorkforceRegistry(default_virtual_workforce())
    worker_metrics.configure(tmp_path)
    try:
        def crash_qa(*args):
            raise RuntimeError("verification unavailable")

        runtime = VirtualWorkerRuntime(
            registry,
            executors={"dev-01": make_local_text_executor(lambda *args: "I did it")},
            qa_executor=crash_qa,
        )
        outcome = runtime.run(_item("qa-crash"))
        assert outcome.stage is WorkStage.BLOCKED
        assert "RuntimeError" in outcome.reason
        assert registry.get("dev-01").is_available
        assert registry.get("qa-01").is_available
        assert worker_metrics.summary(tmp_path)["dev-01"]["successes"] == 0
        assert worker_metrics.summary(tmp_path)["dev-01"]["failures"] == 1
    finally:
        worker_metrics.configure(None)


def test_success_from_another_task_cannot_be_credited(tmp_path):
    from ahos.worker_runtime import WorkerExecutionResult

    registry = VirtualWorkforceRegistry(default_virtual_workforce())
    worker_metrics.configure(tmp_path)
    try:
        def forged(item, worker):
            return WorkerExecutionResult(
                task_id="wrong-task", worker_id=worker, success=True,
                summary="I finished someone else's job",
            )

        runtime = VirtualWorkerRuntime(
            registry, executors={"dev-01": forged},
            qa_executor=lambda *args: (_ for _ in ()).throw(AssertionError("QA should not run")),
        )
        outcome = runtime.run(_item("worker-mismatch"))
        assert outcome.stage is WorkStage.BLOCKED
        assert "identity" in outcome.reason
        assert registry.get("dev-01").is_available
        assert worker_metrics.summary(tmp_path)["dev-01"]["successes"] == 0
    finally:
        worker_metrics.configure(None)


def test_qa_claim_for_another_task_cannot_approve_delivery(tmp_path):
    registry = VirtualWorkforceRegistry(default_virtual_workforce())
    worker_metrics.configure(tmp_path)
    try:
        def forged_qa(item, result, verifier):
            return QaExecutionResult(
                task_id="wrong-task", qa_worker_id=verifier,
                passed=True, summary="looks good",
            )

        runtime = VirtualWorkerRuntime(
            registry,
            executors={"dev-01": make_local_text_executor(lambda *args: "written")},
            qa_executor=forged_qa,
        )
        outcome = runtime.run(_item("qa-mismatch"))
        assert outcome.stage is WorkStage.BLOCKED
        assert "identity" in outcome.reason
        assert registry.get("qa-01").is_available
        assert worker_metrics.summary(tmp_path)["dev-01"]["successes"] == 0
    finally:
        worker_metrics.configure(None)
