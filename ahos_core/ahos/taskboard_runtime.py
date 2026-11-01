"""Optional durable claim gate for mission steps. No network or paid calls."""
from __future__ import annotations

import os
import socket
import threading
import time
import uuid
from pathlib import Path
from typing import Callable, TypeVar

from .taskboard import TaskBoard, TaskBoardError
from .mission_guard import current
from .workforce_execution import WorkItem, WorkStage

T = TypeVar("T")
LEASE_SECONDS = 120


def run_with_claim(board_path: str | Path, item: WorkItem, execute: Callable[[], T]) -> T:
    """Permit only one active runner for this specific mission step.

    The worker remains subject to its normal owner/QA gates. The heartbeater
    holds the task lease during long operations without blocking the worker.
    """
    # Context variables do not propagate to a new heartbeat thread. Capture
    # this mission's token explicitly; never consult another thread's context.
    token = current()

    def guard_mission() -> None:
        if token is not None:
            token.guard()

    guard_mission()
    board = TaskBoard(board_path)
    actor = f"mission:{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:10]}"
    task = board.claim_task(item.task_id, item.title, actor, lease_seconds=LEASE_SECONDS)
    if task is None:
        existing = board.get(item.task_id)
        state = existing.state if existing else "unknown"
        raise TaskBoardError(f"görev başka işçide veya kapalı: {item.task_id} ({state})")

    stop = threading.Event()
    heartbeat_error: list[str] = []

    def pulse() -> None:
        interval = LEASE_SECONDS / 3
        next_heartbeat = time.monotonic() + interval
        while not stop.wait(min(1.0, interval)):
            try:
                guard_mission()
                if time.monotonic() < next_heartbeat:
                    continue
                board.heartbeat(item.task_id, actor, lease_seconds=LEASE_SECONDS, validate=guard_mission)
                next_heartbeat = time.monotonic() + interval
            except Exception as exc:
                heartbeat_error.append(str(exc))
                # Lost ownership must also fence cooperative artifact writes.
                if token is not None:
                    token.revoke()
                break

    thread = threading.Thread(target=pulse, daemon=True, name="ahos-taskboard-heartbeat")
    try:
        guard_mission()
        board.heartbeat(item.task_id, actor, lease_seconds=LEASE_SECONDS, validate=guard_mission)
        thread.start()
        guard_mission()
        result = execute()
        # An executor may ignore cancellation and return a success anyway.
        # Its result must not turn a revoked mission into a completed task.
        guard_mission()
        if heartbeat_error:
            raise TaskBoardError("görev sahipliği kaybedildi: " + heartbeat_error[0])
        if result.stage is WorkStage.COMPLETED:
            qa = result.qa_result
            producer = result.worker_result
            evidence = [f"producer={result.assignment.worker_id}", f"qa={qa.qa_worker_id if qa else 'none'}"]
            if qa:
                evidence.append("qa_result=" + qa.summary)
            board.complete(
                item.task_id, actor, evidence=evidence,
                files=list(producer.artifacts) if producer else [],
                test_command="AHOS independent QA lifecycle",
                validate=guard_mission,
            )
        elif result.assignment.owner_approval_required:
            board.release(item.task_id, actor, validate=guard_mission)
        else:
            board.fail(item.task_id, actor, result.reason or "mission blocked")
        return result
    except BaseException as exc:
        try:
            board.fail(item.task_id, actor, str(exc)[:300])
        except TaskBoardError:
            pass
        raise
    finally:
        stop.set()
        if thread.ident is not None:
            thread.join(timeout=1)
