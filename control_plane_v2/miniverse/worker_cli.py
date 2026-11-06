from __future__ import annotations

import argparse
import asyncio

from .config import Settings
from .queue import SQLiteTaskQueue
from .worker import PersistentWorker, PipelineTaskExecutor, enqueue_coding_task, task_to_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Miniverse persistent worker")
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run", help="Run the worker until stopped")
    run_parser.add_argument("--owner", default="")

    enqueue_parser = sub.add_parser("enqueue", help="Enqueue a coding task")
    enqueue_parser.add_argument("task")
    enqueue_parser.add_argument("--workspace", required=True)
    enqueue_parser.add_argument("--max-attempts", type=int, default=3)

    status_parser = sub.add_parser("status", help="Print one task record")
    status_parser.add_argument("task_id")

    args = parser.parse_args()
    settings = Settings()

    if args.command == "enqueue":
        task_id = enqueue_coding_task(
            settings.queue_db_path,
            task=args.task,
            workspace=args.workspace,
            max_attempts=args.max_attempts,
        )
        print(task_id)
        return

    queue = SQLiteTaskQueue(settings.queue_db_path)

    if args.command == "status":
        task = queue.get(args.task_id)
        if task is None:
            raise SystemExit(f"Task not found: {args.task_id}")
        print(task_to_json(task))
        return

    missing = settings.missing_runtime_settings()
    if missing:
        raise SystemExit("Missing runtime settings: " + ", ".join(missing))

    worker = PersistentWorker(
        queue,
        PipelineTaskExecutor(settings=settings),
        owner=args.owner or None,
        lease_seconds=settings.worker_lease_seconds,
        heartbeat_seconds=settings.worker_heartbeat_seconds,
        retry_base_seconds=settings.worker_retry_base_seconds,
        poll_seconds=settings.worker_poll_seconds,
        health_file=settings.worker_health_file,
    )
    asyncio.run(worker.run_forever())


if __name__ == "__main__":
    main()
