"""Cross-agent task contract on a single JSON file.

Two agents (Codex, DeepSeek, or two sessions of either) may work on the same
holding. This board is the shared, durable answer to "who is doing what":

* one JSON file, written atomically under an OS byte lock,
* a task can be claimed by exactly one owner at a time,
* claims carry a lease; an expired lease may be reclaimed,
* completion requires evidence (files / test command), so a task cannot be
  closed with a prose claim.

It deliberately stays small: no server, no database, no network.
"""

from __future__ import annotations

import json
import math
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

try:  # pragma: no cover - platform import
    import msvcrt
except ImportError:  # pragma: no cover - posix
    msvcrt = None  # type: ignore[assignment]

QUEUED = "queued"
CLAIMED = "claimed"
RUNNING = "running"
DONE = "done"
BLOCKED = "blocked"

TERMINAL = {DONE, BLOCKED}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Task:
    task_id: str
    title: str
    state: str = QUEUED
    owner: str = ""
    created_at: str = ""
    updated_at: str = ""
    lease_until: float = 0.0
    attempts: int = 0
    files: list[str] = field(default_factory=list)
    test_command: str = ""
    evidence: list[str] = field(default_factory=list)
    reason: str = ""
    dedupe_key: str = ""
    history: list[dict[str, object]] = field(default_factory=list)

    @property
    def is_lease_expired(self) -> bool:
        return self.state in {CLAIMED, RUNNING} and self.lease_until <= time.time()

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "Task":
        known = {key: payload[key] for key in cls.__dataclass_fields__ if key in payload}
        return cls(**known)  # type: ignore[arg-type]


class TaskBoardError(RuntimeError):
    pass


class TaskBoard:
    """Durable claim board; every mutation is serialized by an OS file lock."""

    def __init__(self, path: str | Path, *, lock_timeout: float = 10.0) -> None:
        self.path = Path(path)
        self.lock_path = self.path.with_suffix(self.path.suffix + ".lock")
        self.lock_timeout = float(lock_timeout)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ locking
    def _try_lock(self, handle) -> bool:
        if msvcrt is not None:
            try:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                return True
            except OSError:
                return False
        import fcntl  # pragma: no cover - posix

        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            return False

    def _unlock(self, handle) -> None:
        if msvcrt is not None:
            try:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
            return
        import fcntl  # pragma: no cover - posix

        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass

    def _locked(self, mutate, *, write: bool = True):
        deadline = time.monotonic() + self.lock_timeout
        handle = self.lock_path.open("a+b")
        try:
            while True:
                if self._try_lock(handle):
                    break
                if time.monotonic() >= deadline:
                    raise TaskBoardError("görev panosu kilidi alınamadı")
                time.sleep(0.02)
            tasks = self._load()
            result = mutate(tasks)
            if write:
                self._save(tasks)
            return result
        finally:
            self._unlock(handle)
            handle.close()

    # -------------------------------------------------------------- persistence
    def _load(self) -> dict[str, Task]:
        if not self.path.exists():
            return {}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise TaskBoardError("görev panosu okunamıyor; mevcut veriler korunuyor") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("tasks"), list):
            raise TaskBoardError("görev panosu biçimi geçersiz; mevcut veriler korunuyor")
        tasks: dict[str, Task] = {}
        for row in payload["tasks"]:
            if not isinstance(row, dict) or not isinstance(row.get("task_id"), str) or not row["task_id"]:
                raise TaskBoardError("görev panosu içinde geçersiz görev var")
            ident = row["task_id"]
            if ident in tasks:
                raise TaskBoardError(f"görev panosunda yinelenen görev: {ident}")
            try:
                tasks[ident] = Task.from_dict(row)
            except (TypeError, ValueError) as exc:
                raise TaskBoardError(f"görev panosunda geçersiz kayıt: {ident}") from exc
        return tasks

    def _save(self, tasks: dict[str, Task]) -> None:
        payload = {
            "version": 1,
            "updated_at": _now_iso(),
            "tasks": [task.to_dict() for task in tasks.values()],
        }
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.path)

    # --------------------------------------------------------------------- API
    @staticmethod
    def _event(task: Task, action: str, actor: str, *, previous_owner: str = "") -> None:
        task.history.append({
            "at": _now_iso(),
            "action": action,
            "actor": actor,
            "previous_owner": previous_owner,
        })

    @staticmethod
    def _lease(lease_seconds: float) -> float:
        seconds = float(lease_seconds)
        if not math.isfinite(seconds) or seconds <= 0:
            raise ValueError("görev süresi pozitif ve sonlu olmalı")
        return seconds

    def enqueue(
        self, title: str, *, task_id: str | None = None, dedupe_key: str = ""
    ) -> Task:
        title = title.strip()
        key = dedupe_key.strip().casefold()
        if not title:
            raise ValueError("görev başlığı boş olamaz")

        def mutate(tasks: dict[str, Task]) -> Task:
            # A stable job key makes repeated ingestion idempotent.
            if key:
                for existing in tasks.values():
                    if existing.dedupe_key == key and existing.state not in TERMINAL:
                        return existing
            ident = task_id or f"{datetime.now(timezone.utc):%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}"
            if ident in tasks:
                raise TaskBoardError(f"görev zaten var: {ident}")
            task = Task(task_id=ident, title=title, created_at=_now_iso(), updated_at=_now_iso(), dedupe_key=key)
            self._event(task, "created", "")
            tasks[ident] = task
            return task

        return self._locked(mutate)

    def tasks(self, *, state: str | None = None) -> tuple[Task, ...]:
        return tuple(self._locked(lambda tasks: self._select(tasks, state), write=False))

    @staticmethod
    def _select(tasks: dict[str, Task], state: str | None) -> list[Task]:
        rows = [task for task in tasks.values() if state is None or task.state == state]
        return sorted(rows, key=lambda task: task.created_at)

    def get(self, task_id: str) -> Task | None:
        return self._locked(lambda tasks: tasks.get(task_id), write=False)

    def claim(self, owner: str, *, lease_seconds: float = 900) -> Task | None:
        owner = owner.strip()
        if not owner:
            raise ValueError("owner boş olamaz")
        lease = self._lease(lease_seconds)

        def mutate(tasks: dict[str, Task]) -> Task | None:
            candidates = self._select(tasks, None)
            for task in candidates:
                if task.state == QUEUED or (task.state in {CLAIMED, RUNNING} and task.is_lease_expired):
                    previous_owner = task.owner
                    expired = task.state in {CLAIMED, RUNNING}
                    task.state = CLAIMED
                    task.owner = owner
                    task.attempts += 1
                    task.lease_until = time.time() + lease
                    task.updated_at = _now_iso()
                    task.reason = ""
                    self._event(task, "reclaimed" if expired else "claimed", owner, previous_owner=previous_owner)
                    return task
            return None

        return self._locked(mutate)

    def _owned(self, tasks: dict[str, Task], task_id: str, owner: str) -> Task:
        task = tasks.get(task_id)
        if task is None:
            raise TaskBoardError(f"görev yok: {task_id}")
        if task.state not in {CLAIMED, RUNNING}:
            raise TaskBoardError(f"görev aktif olarak sahiplenilmemiş: {task.state}")
        if task.owner != owner.strip():
            raise TaskBoardError(f"görev başka sahipte: {task.owner or '-'}")
        if task.is_lease_expired:
            raise TaskBoardError("görev süresi dolmuş; yeniden sahiplenilmeli")
        return task

    def heartbeat(self, task_id: str, owner: str, *, lease_seconds: float = 900) -> Task:
        lease = self._lease(lease_seconds)

        def mutate(tasks: dict[str, Task]) -> Task:
            task = self._owned(tasks, task_id, owner)
            if task.state != RUNNING:
                self._event(task, "started", owner)
            task.state = RUNNING
            task.lease_until = time.time() + lease
            task.updated_at = _now_iso()
            return task

        return self._locked(mutate)

    def complete(
        self,
        task_id: str,
        owner: str,
        *,
        evidence: list[str],
        files: list[str] | None = None,
        test_command: str = "",
    ) -> Task:
        if not evidence or not any(str(item).strip() for item in evidence):
            raise ValueError("kanıtsız görev tamamlanamaz (evidence gerekli)")

        def mutate(tasks: dict[str, Task]) -> Task:
            task = self._owned(tasks, task_id, owner)
            task.state = DONE
            task.evidence = [str(item) for item in evidence]
            task.files = [str(item) for item in (files or ())]
            task.test_command = str(test_command)
            task.lease_until = 0.0
            task.updated_at = _now_iso()
            self._event(task, "completed", owner)
            return task

        return self._locked(mutate)

    def fail(self, task_id: str, owner: str, reason: str) -> Task:
        def mutate(tasks: dict[str, Task]) -> Task:
            task = self._owned(tasks, task_id, owner)
            task.state = BLOCKED
            task.reason = reason.strip()[:300]
            task.evidence = [reason.strip()[:300]] if reason.strip() else []
            task.lease_until = 0.0
            task.updated_at = _now_iso()
            self._event(task, "blocked", owner)
            return task

        return self._locked(mutate)

    def release(self, task_id: str, owner: str) -> Task:
        def mutate(tasks: dict[str, Task]) -> Task:
            task = self._owned(tasks, task_id, owner)
            task.state = QUEUED
            task.owner = ""
            task.lease_until = 0.0
            task.updated_at = _now_iso()
            self._event(task, "released", owner)
            return task

        return self._locked(mutate)

    def handoff(
        self, task_id: str, owner: str, next_owner: str, *, lease_seconds: float = 900
    ) -> Task:
        """Atomically transfer an active task; previous owner loses write authority."""
        next_owner = next_owner.strip()
        if not next_owner or next_owner == owner.strip():
            raise ValueError("yeni sahip farklı ve boş olmayan bir kimlik olmalı")
        lease = self._lease(lease_seconds)

        def mutate(tasks: dict[str, Task]) -> Task:
            task = self._owned(tasks, task_id, owner)
            previous_owner = task.owner
            task.owner = next_owner
            task.state = CLAIMED
            task.lease_until = time.time() + lease
            task.updated_at = _now_iso()
            task.attempts += 1
            self._event(task, "handed_off", next_owner, previous_owner=previous_owner)
            return task

        return self._locked(mutate)

    def claim_task(
        self, task_id: str, title: str, owner: str, *, lease_seconds: float = 900
    ) -> Task | None:
        """Atomically create/claim one specific task; never pick unrelated work."""
        ident, actor = task_id.strip(), owner.strip()
        if not ident or not actor or not title.strip():
            raise ValueError("task, title ve owner boş olamaz")
        lease = self._lease(lease_seconds)

        def mutate(tasks: dict[str, Task]) -> Task | None:
            task = tasks.get(ident)
            if task is None:
                task = Task(
                    task_id=ident, title=title.strip(),
                    created_at=_now_iso(), updated_at=_now_iso(),
                )
                tasks[ident] = task
                self._event(task, "created", "")
            if task.state != QUEUED and not task.is_lease_expired:
                return None
            previous_owner = task.owner
            action = "reclaimed" if task.is_lease_expired else "claimed"
            task.owner = actor
            task.state = CLAIMED
            task.attempts += 1
            task.lease_until = time.time() + lease
            task.updated_at = _now_iso()
            self._event(task, action, actor, previous_owner=previous_owner)
            return task

        return self._locked(mutate)


def _render(tasks: tuple[Task, ...]) -> str:
    if not tasks:
        return "(görev yok)"
    lines = []
    for task in tasks:
        owner = f" @{task.owner}" if task.owner else ""
        lines.append(f"{task.state:8} {task.task_id}  {task.title}{owner}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        prog="ahos-taskboard",
        description="Codex/DeepSeek ortak görev panosu: sahiplen, ilerlet, kanıtla kapat.",
    )
    parser.add_argument("--board", default=str(Path.cwd() / "taskboard.json"))
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add", help="yeni görev")
    add.add_argument("title")
    add.add_argument("--key", default="", help="tekrarları önleyen sabit iş anahtarı")

    listing = sub.add_parser("list", help="görevleri listele")
    listing.add_argument("--state", default=None)

    claim = sub.add_parser("claim", help="sıradaki görevi sahiplen")
    claim.add_argument("owner")
    claim.add_argument("--lease", type=float, default=900)

    heartbeat = sub.add_parser("heartbeat", help="sahipliği canlı tut")
    heartbeat.add_argument("task_id")
    heartbeat.add_argument("owner")
    heartbeat.add_argument("--lease", type=float, default=900)

    handoff = sub.add_parser("handoff", help="görevi başka işçiye devret")
    handoff.add_argument("task_id")
    handoff.add_argument("owner")
    handoff.add_argument("next_owner")
    handoff.add_argument("--lease", type=float, default=900)

    release = sub.add_parser("release", help="görevi yeniden kuyruğa bırak")
    release.add_argument("task_id")
    release.add_argument("owner")

    history = sub.add_parser("history", help="görevin sahiplik ve durum geçmişi")
    history.add_argument("task_id")

    done = sub.add_parser("complete", help="kanıtla tamamla")
    done.add_argument("task_id")
    done.add_argument("owner")
    done.add_argument("--evidence", action="append", required=True)
    done.add_argument("--file", action="append", default=[])
    done.add_argument("--test", default="")

    fail = sub.add_parser("fail", help="engel kaydıyla kapat")
    fail.add_argument("task_id")
    fail.add_argument("owner")
    fail.add_argument("reason")

    args = parser.parse_args(argv)
    board = TaskBoard(args.board)

    if args.command == "add":
        task = board.enqueue(args.title, dedupe_key=args.key)
        print(f"eklendi: {task.task_id}")
    elif args.command == "list":
        print(_render(board.tasks(state=args.state)))
    elif args.command == "claim":
        task = board.claim(args.owner, lease_seconds=args.lease)
        print(f"sahiplenildi: {task.task_id} -> {task.title}" if task else "(uygun görev yok)")
        return 0 if task else 1
    elif args.command == "heartbeat":
        task = board.heartbeat(args.task_id, args.owner, lease_seconds=args.lease)
        print(f"canlı: {task.task_id} @{task.owner}")
    elif args.command == "handoff":
        task = board.handoff(args.task_id, args.owner, args.next_owner, lease_seconds=args.lease)
        print(f"devredildi: {task.task_id} -> @{task.owner}")
    elif args.command == "release":
        task = board.release(args.task_id, args.owner)
        print(f"kuyruğa döndü: {task.task_id}")
    elif args.command == "history":
        task = board.get(args.task_id)
        if task is None:
            raise TaskBoardError(f"görev yok: {args.task_id}")
        print(json.dumps(task.history, ensure_ascii=False, indent=2))
    elif args.command == "complete":
        task = board.complete(
            args.task_id,
            args.owner,
            evidence=args.evidence,
            files=args.file,
            test_command=args.test,
        )
        print(f"tamamlandı: {task.task_id}")
    elif args.command == "fail":
        task = board.fail(args.task_id, args.owner, args.reason)
        print(f"engellendi: {task.task_id}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
