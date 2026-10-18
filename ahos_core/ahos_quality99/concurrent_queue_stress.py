from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
import threading

from ahos.coding_supervisor import CodingSupervisorStore, CodingTaskStatus
from ahos.coding_worker import CodingBacklogItem


@dataclass(frozen=True, slots=True)
class ConcurrentQueueReport:
    requested: int
    workers: int
    claimed: int
    unique_claims: int
    duplicates: int
    lost: int
    passed: bool


def run_concurrent_queue_stress(*, task_count: int = 100, workers: int = 4) -> ConcurrentQueueReport:
    if task_count < 1 or workers < 2:
        raise ValueError("task_count must be positive and workers >= 2")

    with TemporaryDirectory(prefix="ahos-q99-concurrent-") as tmp:
        root = Path(tmp)
        repo = root / "repo"
        repo.mkdir()
        store = CodingSupervisorStore(
            root / "queue.json",
            lock_timeout_seconds=10,
            stale_lock_seconds=60,
        )
        for index in range(task_count):
            store.enqueue(
                CodingBacklogItem(
                    task_id=f"Q99-C-{index:04d}",
                    title=f"concurrent synthetic {index}",
                    repository=repo,
                    allowed_paths=(f"parallel/{index:04d}",),
                    test_commands=(),
                ),
                idempotency_key=f"q99-concurrent:{index}",
                max_attempts=1,
            )

        claims: list[str] = []
        claims_lock = threading.Lock()

        def worker(worker_index: int) -> None:
            worker_id = f"synthetic-{worker_index}"
            while True:
                record = store.claim(worker_id, lease_seconds=30)
                if record is None:
                    return
                with claims_lock:
                    claims.append(record.task_id)
                store.finish(record.task_id, worker_id, success=False, reason="synthetic")

        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(worker, range(workers)))

        final = store.all()
        unique = len(set(claims))
        duplicates = len(claims) - unique
        lost = task_count - len(final)
        terminal = sum(row.status is CodingTaskStatus.RETRIES_EXHAUSTED for row in final)
        passed = (
            len(claims) == task_count
            and unique == task_count
            and duplicates == 0
            and lost == 0
            and terminal == task_count
        )
        return ConcurrentQueueReport(
            requested=task_count,
            workers=workers,
            claimed=len(claims),
            unique_claims=unique,
            duplicates=duplicates,
            lost=lost,
            passed=passed,
        )
