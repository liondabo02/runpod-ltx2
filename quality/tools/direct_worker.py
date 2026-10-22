"""Measure the model worker directly, without the mission queue.

The queue path is temporarily unreliable in another agent's uncommitted code
(blocked/pending rows cannot be reclaimed). This harness exercises the worker
itself: prompt -> model -> validated edits -> QA, and reports whether files
actually changed.

Usage:
    python quality/tools/direct_worker.py "görev metni" ...
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ahos_core"))

from ahos.daemon import _load_model_env  # noqa: E402
from ahos.delivery import snapshot_tree  # noqa: E402
from ahos.llm_executor import load_settings, make_model_executor  # noqa: E402


class _Item:
    def __init__(self, task_id: str, title: str) -> None:
        self.task_id = task_id
        self.title = title


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    tasks = [item for item in sys.argv[1:] if item.strip()]
    if not tasks:
        print("kullanım: direct_worker.py \"görev\" ...")
        return 2

    runtime = ROOT / "ahos_core" / "runtime"
    _load_model_env(runtime)
    settings = load_settings()
    if settings is None:
        print("model yapılandırılmadı")
        return 2

    project = runtime / "projects" / "mipiluna"
    artifacts = runtime / "artifacts" / "direct-worker"
    artifacts.mkdir(parents=True, exist_ok=True)
    executor = make_model_executor(
        project,
        artifacts,
        settings=settings,
        spend_ledger=runtime / "model-spend.jsonl",
        require_approval_over_files=3,
    )

    rows: list[dict] = []
    for index, task in enumerate(tasks, start=1):
        before = snapshot_tree(project)
        started = time.time()
        result = executor(_Item(f"oyun:direct-{index}:produce", task), "direct-worker")
        elapsed = round(time.time() - started, 1)
        after = snapshot_tree(project)
        changed = len(set(before.files.items()) ^ set(after.files.items())) // 2
        row = {
            "task": task,
            "success": bool(getattr(result, "success", False)),
            "summary": str(getattr(result, "summary", ""))[:200],
            "seconds": elapsed,
            "changed_hint": changed,
        }
        rows.append(row)
        print(f"[{'ok' if row['success'] else 'fail'}] {elapsed}s · {task[:60]}")
        print(f"    {row['summary'][:160]}")

    ok = sum(1 for row in rows if row["success"])
    print("\nözet:")
    print(f"  görev: {len(rows)}")
    print(f"  başarılı: {ok} ({ok / len(rows):.0%})")
    print(f"  ortalama: {sum(r['seconds'] for r in rows) / len(rows):.1f} sn")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
