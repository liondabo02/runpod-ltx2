from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from ahos.coding_memory import CodingMemory


@dataclass(frozen=True, slots=True)
class MemoryDurabilityReport:
    persisted_after_reopen: bool
    secret_redacted: bool
    repository_isolated: bool
    passed: bool


def run_memory_durability_rehearsal() -> MemoryDurabilityReport:
    with TemporaryDirectory(prefix="ahos-q99-memory-") as tmp:
        root = Path(tmp)
        db_path = root / "memory.sqlite3"
        repo_a = root / "repo-a"
        repo_b = root / "repo-b"
        repo_a.mkdir()
        repo_b.mkdir()

        task = SimpleNamespace(
            repository=str(repo_a),
            task_id="MEM-001",
            attempts=1,
            title="Repair worker token=VERY_SECRET_VALUE",
            base_ref="HEAD",
        )

        first = CodingMemory(db_path)
        first.record_failure(task, "provider failed password=DO_NOT_STORE")
        context_before = first.context(repo_a, "Repair worker", limit=3000)

        reopened = CodingMemory(db_path)
        context_after = reopened.context(repo_a, "Repair worker", limit=3000)
        other_repo = reopened.context(repo_b, "Repair worker", limit=3000)

        persisted = "MEM-001" in context_before and "MEM-001" in context_after
        redacted = (
            "VERY_SECRET_VALUE" not in context_after
            and "DO_NOT_STORE" not in context_after
            and "[REDACTED]" in context_after
        )
        isolated = "MEM-001" not in other_repo
        return MemoryDurabilityReport(
            persisted_after_reopen=persisted,
            secret_redacted=redacted,
            repository_isolated=isolated,
            passed=persisted and redacted and isolated,
        )
