from __future__ import annotations

import hashlib
import argparse
import json
import os
import time
import uuid
import subprocess
from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Callable, Iterator, Sequence

from .coding_worker import AutonomousCodingWorker, CodingBacklogItem, CodingWorkerStatus


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None = None) -> str:
    return (value or _now()).isoformat()


class CodingTaskStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_OWNER_APPROVAL = "waiting_owner_approval"
    OWNER_APPROVED = "owner_approved"
    OWNER_REJECTED = "owner_rejected"
    RETRIES_EXHAUSTED = "retries_exhausted"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class CodingTaskRecord:
    task_id: str
    idempotency_key: str
    title: str
    repository: str
    base_ref: str
    allowed_paths: tuple[str, ...]
    test_commands: tuple[tuple[str, ...], ...]
    status: CodingTaskStatus
    attempts: int
    max_attempts: int
    priority: int
    claimed_by: str | None
    lease_expires_at: str | None
    last_error: str | None
    worktree: str | None
    patch_file: str | None
    approval_file: str | None
    evidence_sha256: str | None
    owner_decision_at: str | None
    created_at: str
    updated_at: str

    def backlog_item(self) -> CodingBacklogItem:
        return CodingBacklogItem(
            task_id=self.task_id,
            title=self.title,
            repository=Path(self.repository),
            base_ref=self.base_ref,
            allowed_paths=self.allowed_paths,
            test_commands=self.test_commands,
        )


class CodingSupervisorStore:
    """Small durable queue with cross-process atomic claims.

    A sibling lock file serializes read-modify-write operations and JSON is
    replaced atomically. The queue is local-only and performs no Git or network
    side effects.
    """

    def __init__(self, path: str | Path, *, lock_timeout_seconds: float = 5.0,
                 stale_lock_seconds: float = 30.0) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_path = self.path.with_suffix(self.path.suffix + ".lock")
        self.lock_timeout_seconds = lock_timeout_seconds
        self.stale_lock_seconds = stale_lock_seconds

    @contextmanager
    def _locked(self) -> Iterator[None]:
        deadline = time.monotonic() + self.lock_timeout_seconds
        while True:
            try:
                fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, f"{os.getpid()}\n".encode("ascii"))
                os.close(fd)
                break
            except FileExistsError:
                try:
                    age = time.time() - self.lock_path.stat().st_mtime
                    if age >= self.stale_lock_seconds:
                        self.lock_path.unlink(missing_ok=True)
                        continue
                except FileNotFoundError:
                    continue
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"coding queue lock timeout: {self.lock_path}")
                time.sleep(0.01)
        try:
            yield
        finally:
            self.lock_path.unlink(missing_ok=True)

    def _load(self) -> dict[str, CodingTaskRecord]:
        if not self.path.exists():
            return {}
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("coding supervisor queue must be a JSON object")
        records: dict[str, CodingTaskRecord] = {}
        for key, item in raw.items():
            records[key] = CodingTaskRecord(
                task_id=item["task_id"], idempotency_key=item["idempotency_key"],
                title=item["title"], repository=item["repository"],
                base_ref=item["base_ref"], allowed_paths=tuple(item["allowed_paths"]),
                test_commands=tuple(tuple(c) for c in item["test_commands"]),
                status=CodingTaskStatus(item["status"]), attempts=int(item["attempts"]),
                max_attempts=int(item["max_attempts"]), priority=int(item["priority"]),
                claimed_by=item.get("claimed_by"), lease_expires_at=item.get("lease_expires_at"),
                last_error=item.get("last_error"), worktree=item.get("worktree"),
                patch_file=item.get("patch_file"), approval_file=item.get("approval_file"),
                evidence_sha256=item.get("evidence_sha256"),
                owner_decision_at=item.get("owner_decision_at"),
                created_at=item["created_at"], updated_at=item["updated_at"],
            )
        return records

    def _save(self, records: dict[str, CodingTaskRecord]) -> None:
        body: dict[str, object] = {}
        for key in sorted(records):
            item = asdict(records[key])
            item["status"] = records[key].status.value
            body[key] = item
        tmp = self.path.with_name(f".{self.path.name}.{uuid.uuid4().hex}.tmp")
        tmp.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp, self.path)

    def enqueue(self, item: CodingBacklogItem, *, idempotency_key: str | None = None,
                max_attempts: int = 2, priority: int = 0) -> CodingTaskRecord:
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        key = (idempotency_key or item.task_id).strip()
        if not key:
            raise ValueError("idempotency_key must not be empty")
        with self._locked():
            records = self._load()
            existing = next((r for r in records.values() if r.idempotency_key == key), None)
            if existing:
                requested = (
                    item.task_id, item.title, str(Path(item.repository).resolve()), item.base_ref,
                    item.allowed_paths, item.test_commands, max_attempts, priority,
                )
                persisted = (
                    existing.task_id, existing.title, existing.repository, existing.base_ref,
                    existing.allowed_paths, existing.test_commands,
                    existing.max_attempts, existing.priority,
                )
                if requested != persisted:
                    raise ValueError("idempotency key reused with different task payload")
                return existing
            if item.task_id in records:
                raise ValueError(f"duplicate task_id with different idempotency key: {item.task_id}")
            when = _iso()
            record = CodingTaskRecord(
                task_id=item.task_id, idempotency_key=key, title=item.title,
                repository=str(Path(item.repository).resolve()), base_ref=item.base_ref,
                allowed_paths=item.allowed_paths, test_commands=item.test_commands,
                status=CodingTaskStatus.QUEUED, attempts=0, max_attempts=max_attempts,
                priority=priority, claimed_by=None, lease_expires_at=None, last_error=None,
                worktree=None, patch_file=None, approval_file=None, evidence_sha256=None,
                owner_decision_at=None, created_at=when, updated_at=when,
            )
            records[item.task_id] = record
            self._save(records)
            return record

    def claim(self, worker_id: str, *, lease_seconds: int = 900) -> CodingTaskRecord | None:
        if not worker_id.strip() or lease_seconds < 1:
            raise ValueError("worker_id and a positive lease are required")
        with self._locked():
            records = self._load()
            now = _now()
            for key, record in tuple(records.items()):
                if record.status is CodingTaskStatus.RUNNING and record.lease_expires_at:
                    if datetime.fromisoformat(record.lease_expires_at) <= now:
                        status = (CodingTaskStatus.QUEUED if record.attempts < record.max_attempts
                                  else CodingTaskStatus.RETRIES_EXHAUSTED)
                        records[key] = replace(record, status=status, claimed_by=None,
                                               lease_expires_at=None,
                                               last_error="worker lease expired", updated_at=_iso(now))
            candidates = [r for r in records.values() if r.status is CodingTaskStatus.QUEUED]
            if not candidates:
                self._save(records)
                return None
            selected = sorted(candidates, key=lambda r: (-r.priority, r.created_at, r.task_id))[0]
            claimed = replace(selected, status=CodingTaskStatus.RUNNING,
                              attempts=selected.attempts + 1, claimed_by=worker_id,
                              lease_expires_at=_iso(now + timedelta(seconds=lease_seconds)),
                              updated_at=_iso(now))
            records[selected.task_id] = claimed
            self._save(records)
            return claimed

    def finish(self, task_id: str, worker_id: str, *, success: bool, reason: str,
               worktree: Path | None = None, patch_file: Path | None = None,
               approval_file: Path | None = None) -> CodingTaskRecord:
        with self._locked():
            records = self._load()
            current = records.get(task_id)
            if current is None:
                raise KeyError(task_id)
            if current.status is not CodingTaskStatus.RUNNING or current.claimed_by != worker_id:
                raise ValueError("task is not claimed by this worker")
            evidence = None
            if success:
                if not approval_file or not patch_file:
                    raise ValueError("successful task requires approval evidence and patch")
                evidence = hashlib.sha256(Path(approval_file).read_bytes()).hexdigest()
                status = CodingTaskStatus.WAITING_OWNER_APPROVAL
            else:
                status = (CodingTaskStatus.QUEUED if current.attempts < current.max_attempts
                          else CodingTaskStatus.RETRIES_EXHAUSTED)
            updated = replace(
                current, status=status, claimed_by=None, lease_expires_at=None,
                last_error=None if success else reason,
                worktree=str(worktree) if worktree else None,
                patch_file=str(patch_file) if patch_file else None,
                approval_file=str(approval_file) if approval_file else None,
                evidence_sha256=evidence, updated_at=_iso(),
            )
            records[task_id] = updated
            self._save(records)
            return updated

    def record_owner_decision(self, task_id: str, *, approved: bool) -> CodingTaskRecord:
        """Record a decision only; intentionally does not integrate or publish."""
        with self._locked():
            records = self._load()
            current = records.get(task_id)
            if current is None:
                raise KeyError(task_id)
            if current.status is not CodingTaskStatus.WAITING_OWNER_APPROVAL:
                raise ValueError("task is not waiting for owner approval")
            if not current.approval_file or not current.evidence_sha256:
                raise ValueError("owner evidence is missing")
            actual = hashlib.sha256(Path(current.approval_file).read_bytes()).hexdigest()
            if actual != current.evidence_sha256:
                raise ValueError("owner approval evidence was modified")
            approval = json.loads(Path(current.approval_file).read_text(encoding="utf-8"))
            if not current.patch_file or not Path(current.patch_file).is_file():
                raise ValueError("owner review patch is missing")
            patch_digest = hashlib.sha256(Path(current.patch_file).read_bytes()).hexdigest()
            if patch_digest != approval.get("patch_sha256"):
                raise ValueError("owner review patch was modified")
            updated = replace(current,
                              status=(CodingTaskStatus.OWNER_APPROVED if approved
                                      else CodingTaskStatus.OWNER_REJECTED),
                              owner_decision_at=_iso(), updated_at=_iso())
            records[task_id] = updated
            self._save(records)
            return updated

    def all(self) -> tuple[CodingTaskRecord, ...]:
        with self._locked():
            records = self._load()
            return tuple(records[k] for k in sorted(records))

    def get(self, task_id: str) -> CodingTaskRecord | None:
        with self._locked():
            return self._load().get(task_id)

    def status(self) -> dict[str, object]:
        """Stable, JSON-serializable read model for dashboards and operators."""
        records = self.all()
        counts = {status.value: 0 for status in CodingTaskStatus}
        for record in records:
            counts[record.status.value] += 1
        blockers = [
            {"task_id": r.task_id, "status": r.status.value, "reason": r.last_error}
            for r in records
            if r.status is CodingTaskStatus.RETRIES_EXHAUSTED
        ]
        waiting = [
            {"task_id": r.task_id, "approval_file": r.approval_file,
             "patch_file": r.patch_file, "updated_at": r.updated_at}
            for r in records
            if r.status is CodingTaskStatus.WAITING_OWNER_APPROVAL
        ]
        return {
            "counts": counts,
            "blockers": blockers,
            "waiting_approvals": waiting,
            "tasks": [
                {"task_id": r.task_id, "title": r.title, "status": r.status.value,
                 "attempts": r.attempts, "max_attempts": r.max_attempts,
                 "last_error": r.last_error, "patch_file": r.patch_file,
                 "approval_file": r.approval_file, "updated_at": r.updated_at}
                for r in records
            ],
        }


class CodingSupervisor:
    """Claim one queue item, run it in an isolated attempt, then stop for owner."""

    def __init__(self, *, store: CodingSupervisorStore,
                 worker: AutonomousCodingWorker, worker_id: str,
                 test_command_policy: Callable[[Sequence[str]], bool] | None = None) -> None:
        self.store = store
        self.worker = worker
        self.worker_id = worker_id
        # Backlog content is data from outside the execution boundary. Running
        # its argv without an explicit host policy would be arbitrary execution.
        self.test_command_policy = test_command_policy or (lambda _command: False)

    def run_once(self) -> CodingTaskRecord | None:
        claimed = self.store.claim(self.worker_id)
        if claimed is None:
            return None
        rejected = [command for command in claimed.test_commands
                    if not self.test_command_policy(command)]
        if rejected:
            return self.store.finish(
                claimed.task_id, self.worker_id, success=False,
                reason="test command rejected by supervisor policy",
            )
        # A separate root per attempt prevents failed attempts from contaminating retries.
        attempt_worker = AutonomousCodingWorker(
            runner=self.worker.runner,
            workspace_root=self.worker.workspace_root / claimed.task_id / f"attempt-{claimed.attempts}",
        )
        try:
            result = attempt_worker.run(claimed.backlog_item(), self.worker_id)
            ok = result.status is CodingWorkerStatus.WAITING_OWNER_APPROVAL
            return self.store.finish(
                claimed.task_id, self.worker_id, success=ok, reason=result.reason,
                worktree=result.worktree, patch_file=result.patch_file,
                approval_file=result.approval_file,
            )
        except Exception as exc:
            return self.store.finish(
                claimed.task_id, self.worker_id, success=False,
                reason=f"supervisor caught {type(exc).__name__}: {exc}",
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="AHOS local coding supervisor")
    parser.add_argument("--queue", required=True, help="Persistent queue JSON path")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    enqueue = sub.add_parser("enqueue")
    enqueue.add_argument("--task-json", required=True)
    enqueue.add_argument("--idempotency-key")
    enqueue.add_argument("--max-attempts", type=int, default=2)
    enqueue.add_argument("--priority", type=int, default=0)
    run = sub.add_parser("run-once")
    run.add_argument("--workspace", required=True)
    run.add_argument("--worker-id", required=True)
    run.add_argument("--builder-command", nargs="+", required=True)
    run.add_argument("--allow-test-executable", action="append", required=True)
    args = parser.parse_args()
    store = CodingSupervisorStore(args.queue)
    if args.command == "status":
        print(json.dumps(store.status(), indent=2, sort_keys=True))
        return 0
    if args.command == "enqueue":
        raw = json.loads(Path(args.task_json).read_text(encoding="utf-8"))
        item = CodingBacklogItem(
            task_id=raw["task_id"], title=raw["title"], repository=Path(raw["repository"]),
            base_ref=raw.get("base_ref", "HEAD"),
            allowed_paths=tuple(raw["allowed_paths"]),
            test_commands=tuple(tuple(c) for c in raw.get("test_commands", ())),
        )
        record = store.enqueue(item, idempotency_key=args.idempotency_key,
                               max_attempts=args.max_attempts, priority=args.priority)
        print(json.dumps(asdict(record) | {"status": record.status.value}, indent=2))
        return 0

    class _BuilderResult:
        success = True

    def builder(prompt: str, worktree: Path) -> _BuilderResult:
        completed = subprocess.run(args.builder_command, cwd=worktree, input=prompt,
                                   text=True, check=False)
        if completed.returncode:
            raise RuntimeError(f"builder exited with {completed.returncode}")
        return _BuilderResult()

    allowed = {str(Path(value).resolve()) for value in args.allow_test_executable}
    policy = lambda command: bool(command) and str(Path(command[0]).resolve()) in allowed
    result = CodingSupervisor(
        store=store,
        worker=AutonomousCodingWorker(runner=builder, workspace_root=Path(args.workspace)),
        worker_id=args.worker_id,
        test_command_policy=policy,
    ).run_once()
    print(json.dumps(None if result is None else
                     asdict(result) | {"status": result.status.value}, indent=2))
    return 0 if result is None or result.status is CodingTaskStatus.WAITING_OWNER_APPROVAL else 2


if __name__ == "__main__":
    raise SystemExit(main())
