from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from ahos.coding_supervisor import CodingSupervisorStore, CodingTaskStatus
from ahos.coding_worker import CodingBacklogItem


@dataclass(frozen=True, slots=True)
class RecoveryFaultReport:
    lease_expiry_recovered: bool
    idempotent_replay_safe: bool
    lost_tasks: int
    passed: bool


def run_recovery_fault_matrix() -> RecoveryFaultReport:
    """Local-only deterministic recovery rehearsal against an isolated queue."""
    with TemporaryDirectory(prefix="ahos-q99-recovery-") as tmp:
        root = Path(tmp)
        repo = root / "repo"
        repo.mkdir()
        store = CodingSupervisorStore(root / "queue.json")

        item = CodingBacklogItem(
            task_id="Q99-RECOVERY-001",
            title="synthetic interrupted task",
            repository=repo,
            allowed_paths=("isolated/recovery",),
            test_commands=(),
        )
        first = store.enqueue(item, idempotency_key="recovery:1", max_attempts=2)
        replay = store.enqueue(item, idempotency_key="recovery:1", max_attempts=2)
        idempotent = first.task_id == replay.task_id and len(store.all()) == 1

        claimed = store.claim("worker-before-crash", lease_seconds=60)
        if claimed is None:
            return RecoveryFaultReport(False, idempotent, 1, False)

        # Fault injection stays inside the isolated test queue: expire the lease
        # as if the worker process died without completing.
        with store._locked():
            records = store._load()
            current = records[item.task_id]
            records[item.task_id] = replace(
                current,
                lease_expires_at=(datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(),
            )
            store._save(records)

        recovered = store.claim("worker-after-restart", lease_seconds=60)
        lease_ok = (
            recovered is not None
            and recovered.task_id == item.task_id
            and recovered.claimed_by == "worker-after-restart"
            and recovered.attempts == 2
        )
        if recovered is not None:
            store.finish(
                recovered.task_id,
                "worker-after-restart",
                success=False,
                reason="synthetic terminal result after recovery",
            )

        final = store.all()
        lost = 1 - len(final)
        terminal_ok = bool(final and final[0].status is CodingTaskStatus.RETRIES_EXHAUSTED)
        return RecoveryFaultReport(
            lease_expiry_recovered=lease_ok and terminal_ok,
            idempotent_replay_safe=idempotent,
            lost_tasks=lost,
            passed=lease_ok and terminal_ok and idempotent and lost == 0,
        )
