from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import time


@dataclass(frozen=True, slots=True)
class ProcessRecoveryE2EReport:
    first_process_claimed: bool
    second_process_reclaimed: bool
    attempts_after_recovery: int
    lost: bool
    passed: bool


_CHILD1 = r'''
import json, pathlib, sys
from ahos.coding_supervisor import CodingSupervisorStore
from ahos.coding_worker import CodingBacklogItem
queue=pathlib.Path(sys.argv[1])
repo=pathlib.Path(sys.argv[2])
store=CodingSupervisorStore(queue)
item=CodingBacklogItem(
    task_id="Q99-PROC-RECOVERY",
    title="process boundary recovery",
    repository=repo,
    allowed_paths=("isolated/process-recovery",),
    test_commands=(),
)
store.enqueue(item,idempotency_key="q99-proc-recovery",max_attempts=2)
claimed=store.claim("process-one",lease_seconds=1)
print(json.dumps({"claimed": bool(claimed), "attempts": claimed.attempts if claimed else 0}))
'''

_CHILD2 = r'''
import json, pathlib, sys
from ahos.coding_supervisor import CodingSupervisorStore
queue=pathlib.Path(sys.argv[1])
store=CodingSupervisorStore(queue)
claimed=store.claim("process-two",lease_seconds=30)
print(json.dumps({
    "claimed": bool(claimed),
    "task_id": claimed.task_id if claimed else None,
    "worker": claimed.claimed_by if claimed else None,
    "attempts": claimed.attempts if claimed else 0,
}))
if claimed:
    store.finish(claimed.task_id,"process-two",success=False,reason="recovery e2e terminal")
'''


def _run_child(code: str, queue: Path, repo: Path, cwd: Path) -> dict[str, object]:
    completed = subprocess.run(
        [sys.executable, "-c", code, str(queue), str(repo)],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=15,
    )
    if completed.returncode:
        raise RuntimeError(completed.stderr[-2000:])
    return json.loads(completed.stdout.strip())


def run_process_recovery_e2e() -> ProcessRecoveryE2EReport:
    package_root = Path(__file__).resolve().parents[1]
    with TemporaryDirectory(prefix="ahos-q99-process-recovery-") as tmp:
        root = Path(tmp)
        repo = root / "repo"
        repo.mkdir()
        queue = root / "queue.json"

        first = _run_child(_CHILD1, queue, repo, package_root)
        time.sleep(1.25)
        second = _run_child(_CHILD2, queue, repo, package_root)

        from ahos.coding_supervisor import CodingSupervisorStore, CodingTaskStatus
        final = CodingSupervisorStore(queue).get("Q99-PROC-RECOVERY")
        first_ok = first.get("claimed") is True and first.get("attempts") == 1
        second_ok = (
            second.get("claimed") is True
            and second.get("task_id") == "Q99-PROC-RECOVERY"
            and second.get("worker") == "process-two"
            and second.get("attempts") == 2
        )
        lost = final is None
        terminal_ok = final is not None and final.status is CodingTaskStatus.RETRIES_EXHAUSTED
        return ProcessRecoveryE2EReport(
            first_process_claimed=first_ok,
            second_process_reclaimed=second_ok and terminal_ok,
            attempts_after_recovery=int(second.get("attempts") or 0),
            lost=lost,
            passed=first_ok and second_ok and terminal_ok and not lost,
        )
