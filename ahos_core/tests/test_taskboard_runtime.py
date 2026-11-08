from __future__ import annotations

from types import SimpleNamespace

import pytest

from ahos.taskboard import DONE, BLOCKED, TaskBoard, TaskBoardError
from ahos.taskboard_runtime import run_with_claim
from ahos.workforce_execution import WorkItem, WorkStage


def _work():
    return WorkItem(task_id="mission-1:build", title="build", department="software", required_capabilities=frozenset({"python"}))


def _outcome(stage=WorkStage.COMPLETED, approved=False):
    return SimpleNamespace(
        stage=stage,
        assignment=SimpleNamespace(worker_id="codex", owner_approval_required=approved),
        worker_result=SimpleNamespace(artifacts=("artifact.html",)),
        qa_result=SimpleNamespace(qa_worker_id="qa-1", summary="browser passed"),
        reason="owner approval needed" if approved else "OK",
    )


def test_success_persisted_and_replay_blocked(tmp_path):
    path = tmp_path / "board.json"
    work = _work()
    result = run_with_claim(path, work, lambda: _outcome())
    assert result.stage is WorkStage.COMPLETED
    task = TaskBoard(path).get(work.task_id)
    assert task.state == DONE
    assert any("qa=qa-1" in item for item in task.evidence)
    assert any(event["action"] == "completed" for event in task.history)
    with pytest.raises(TaskBoardError):
        run_with_claim(path, work, lambda: pytest.fail("must never run twice"))


def test_owner_approval_blocks_execution_and_requeues(tmp_path):
    path = tmp_path / "board.json"
    work = _work()
    result = run_with_claim(path, work, lambda: _outcome(WorkStage.BLOCKED, approved=True))
    assert result.stage == WorkStage.BLOCKED
    assert TaskBoard(path).get(work.task_id).state == "queued"
    assert run_with_claim(path, work, lambda: _outcome()).stage is WorkStage.COMPLETED


def test_failed_qa_blocks_replay(tmp_path):
    path = tmp_path / "board.json"
    work = _work()
    run_with_claim(path, work, lambda: _outcome(WorkStage.BLOCKED))
    assert TaskBoard(path).get(work.task_id).state == BLOCKED
    with pytest.raises(TaskBoardError):
        run_with_claim(path, work, lambda: pytest.fail("blocked step was re-run"))


def test_concurrent_claim_fails_before_executor(tmp_path):
    from ahos.taskboard import TaskBoard
    path = tmp_path / "board.json"
    work = _work()
    TaskBoard(path).claim_task(work.task_id, work.title, "another-runner")
    with pytest.raises(TaskBoardError):
        run_with_claim(path, work, lambda: pytest.fail("duplicate execution"))
