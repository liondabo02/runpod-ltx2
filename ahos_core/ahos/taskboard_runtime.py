"""Optional durable claim gate for mission steps. No network or paid calls."""
from __future__ import annotations

import os
import socket
import threading
import uuid
from pathlib import Path
from typing import Callable, TypeVar

from .taskboard import TaskBoard, TaskBoardError
from .workforce_execution import WorkItem, WorkStage

T = TypeVar("T")
LEASE_SECONDS = 120


def run_with_claim(board_path: str | Path, item: WorkItem, execute: Callable[[], T]) -> T:
    """Permit only one active runner for this specific mission step.

    The worker remains subject to its normal owner/QA gates. The heartbeater
    holds the task lease during long operations without blocking the worker.
    """
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
        while not stop.wait(LEASE_SECONDS / 3):
            try:
                board.heartbeat(item.task_id, actor, lease_seconds=LEASE_SECONDS)
            except Exception as exc:
                heartbeat_error.append(str(exc))
                break

    thread = threading.Thread(target=pulse, daemon=True, name="ahos-taskboard-heartbeat")
    board.heartbeat(item.task_id, actor, lease_seconds=LEASE_SECONDS)
    thread.start()
    try:
        result = execute()
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
            )
        elif result.assignment.owner_approval_required:
            board.release(item.task_id, actor)
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
        thread.join(timeout=1)
