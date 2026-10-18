from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from ahos.coding_supervisor import CodingSupervisorStore, CodingTaskStatus
from ahos.coding_worker import CodingBacklogItem


@dataclass(frozen=True, slots=True)
class QueueStressReport:
    requested: int
    unique_records: int
    duplicate_records: int
    claimed: int
    terminal: int
    lost: int
    passed: bool


def run_synthetic_queue_stress(*, task_count: int = 100) -> QueueStressReport:
    """Exercise durable queue semantics with zero external/API activity."""
    if task_count < 1:
        raise ValueError("task_count must be positive")

    with TemporaryDirectory(prefix="ahos-quality99-") as tmp:
        root = Path(tmp)
        repo = root / "repo"
        repo.mkdir()
        store = CodingSupervisorStore(root / "queue.json")

        for index in range(task_count):
            item = CodingBacklogItem(
                task_id=f"Q99-{index:04d}",
                title=f"synthetic quality task {index}",
                repository=repo,
                base_ref="HEAD",
                allowed_paths=(f"isolated/{index:04d}",),
                test_commands=(),
            )
            first = store.enqueue(
                item,
                idempotency_key=f"q99:{index:04d}",
                max_attempts=1,
                priority=index % 5,
            )
            second = store.enqueue(
                item,
                idempotency_key=f"q99:{index:04d}",
                max_attempts=1,
                priority=index % 5,
            )
            if first.task_id != second.task_id:
                raise AssertionError("idempotent enqueue changed task identity")

        initial = store.all()
        claimed = 0
        while True:
            record = store.claim("quality99-worker", lease_seconds=30)
            if record is None:
                break
            claimed += 1
            store.finish(
                record.task_id,
                "quality99-worker",
                success=False,
                reason="synthetic terminal outcome",
            )

        final = store.all()
        unique = len({item.task_id for item in final})
        terminal = sum(item.status is CodingTaskStatus.RETRIES_EXHAUSTED for item in final)
        lost = task_count - len(final)
        duplicates = len(final) - unique
        passed = (
            len(initial) == task_count
            and len(final) == task_count
            and unique == task_count
            and claimed == task_count
            and terminal == task_count
            and duplicates == 0
            and lost == 0
        )
        return QueueStressReport(
            requested=task_count,
            unique_records=unique,
            duplicate_records=duplicates,
            claimed=claimed,
            terminal=terminal,
            lost=lost,
            passed=passed,
        )
