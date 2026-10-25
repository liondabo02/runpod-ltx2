"""Idea recovery: a stuck running task must return to the queue."""

from __future__ import annotations

import json
import os
import time

from ahos import ideas
from ahos.owner_console import build_default_console


def test_completed_idea_stays_done(tmp_path) -> None:
    console = build_default_console(tmp_path)
    idea = ideas.submit(console, tmp_path, "oyun için yeni bir bölüm yap")
    for task in idea.tasks:
        ideas.complete(idea.idea_id, task["task_id"], tmp_path, success=True)

    assert ideas.recover(tmp_path) == 0
    assert ideas.pending_tasks(tmp_path) == []


def test_stale_running_task_is_recovered(tmp_path) -> None:
    console = build_default_console(tmp_path)
    idea = ideas.submit(console, tmp_path, "stüdyo için afiş tasarla")
    claimed = ideas.claim_next(tmp_path)
    assert claimed is not None
    path = tmp_path / "ideas" / f"{idea.idea_id}.json"
    old = time.time() - 3600
    os.utime(path, (old, old))

    recovered = ideas.recover(tmp_path, stale_minutes=15)

    assert recovered == 1
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["status"] == "open"
    assert any(task["status"] == "pending" for task in payload["tasks"])
