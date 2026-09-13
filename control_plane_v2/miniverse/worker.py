from __future__ import annotations

import asyncio
import json
import os
import socket
from dataclasses import asdict
from pathlib import Path
from typing import Any, Protocol

from .config import Settings
from .execution import ExecutionResult, MiniverseExecutionPipeline
from .queue import SQLiteTaskQueue, TaskRecord


class TaskExecutor(Protocol):
    async def execute(self, task: TaskRecord) -> dict[str, Any]: ...


class PipelineTaskExecutor:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()
        self.pipeline = MiniverseExecutionPipeline(settings=self.settings)

    async def execute(self, task: TaskRecord) -> dict[str, Any]:
        if task.kind != "coding":
            raise ValueError(f"Unsupported task kind: {task.kind}")
        instruction = str(task.payload.get("task", "")).strip()
        workspace = str(task.payload.get("workspace", "")).strip()
        if not instruction:
            raise ValueError("coding task payload requires 'task'")
        if not workspace:
            raise ValueError("coding task payload requires 'workspace'")
        result = await self.pipeline.execute(instruction, Path(workspace))
        return _execution_result_to_json(result)


def _execution_result_to_json(result: ExecutionResult) -> dict[str, Any]:
    return {
        "task": result.task,
        "preflight_report": result.preflight_report,
        "builder": asdict(result.builder),
        "qa_report": result.qa_report,
        "owner_approval_required": result.owner_approval_required,
        "owner_approval_reasons": list(result.owner_approval_reasons),
    }


class PersistentWorker:
    def __init__(
        self,
        queue: SQLiteTaskQueue,
        executor: TaskExecutor,
        *,
        owner: str | None = None,
        lease_seconds: float = 120.0,
        heartbeat_seconds: float = 30.0,
        retry_base_seconds: float = 15.0,
        poll_seconds: float = 2.0,
    ) -> None:
        if heartbeat_seconds <= 0 or heartbeat_seconds >= lease_seconds:
            raise ValueError("heartbeat_seconds must be > 0 and < lease_seconds")
        if retry_base_seconds < 0:
            raise ValueError("retry_base_seconds must be >= 0")
        if poll_seconds <= 0:
            raise ValueError("poll_seconds must be > 0")
        self.queue = queue
        self.executor = executor
        self.owner = owner or f"{socket.gethostname()}:{os.getpid()}"
        self.lease_seconds = lease_seconds
        self.heartbeat_seconds = heartbeat_seconds
        self.retry_base_seconds = retry_base_seconds
        self.poll_seconds = poll_seconds
        self._stop = asyncio.Event()

    def stop(self) -> None:
        self._stop.set()

    async def run_once(self) -> bool:
        task = self.queue.claim(self.owner, lease_seconds=self.lease_seconds)
        if task is None:
            return False

        heartbeat_task = asyncio.create_task(self._heartbeat_loop(task.id))
        try:
            result = await self.executor.execute(task)
            if not self.queue.complete(task.id, self.owner, result):
                raise RuntimeError(f"Lost lease while completing task {task.id}")
        except Exception as exc:
            delay = self.retry_base_seconds * (2 ** max(task.attempts - 1, 0))
            self.queue.fail(
                task.id,
                self.owner,
                f"{type(exc).__name__}: {exc}",
                retry_delay_seconds=delay,
            )
        finally:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass
        return True

    async def run_forever(self) -> None:
        while not self._stop.is_set():
            worked = await self.run_once()
            if worked:
                continue
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.poll_seconds)
            except asyncio.TimeoutError:
                pass

    async def _heartbeat_loop(self, task_id: str) -> None:
        while True:
            await asyncio.sleep(self.heartbeat_seconds)
            if not self.queue.heartbeat(task_id, self.owner, lease_seconds=self.lease_seconds):
                raise RuntimeError(f"Lost lease for task {task_id}")


def enqueue_coding_task(
    db_path: str | Path,
    *,
    task: str,
    workspace: str | Path,
    max_attempts: int = 3,
) -> str:
    queue = SQLiteTaskQueue(db_path)
    return queue.enqueue(
        "coding",
        {"task": task, "workspace": str(Path(workspace).resolve())},
        max_attempts=max_attempts,
    )


def task_to_json(task: TaskRecord) -> str:
    return json.dumps(asdict(task), indent=2, sort_keys=True)
