from __future__ import annotations

import threading
import time

import pytest

from ahos.taskboard import BLOCKED, DONE, QUEUED, RUNNING, TaskBoard, TaskBoardError


def _board(tmp_path) -> TaskBoard:
    return TaskBoard(tmp_path / "tasks.json")


def test_enqueue_claim_complete_cycle(tmp_path) -> None:
    board = _board(tmp_path)
    task = board.enqueue("Mipiluna: ses düğmesi ekle")

    claimed = board.claim("deepseek")
    assert claimed is not None
    assert claimed.task_id == task.task_id
    assert claimed.owner == "deepseek"
    assert claimed.attempts == 1

    running = board.heartbeat(task.task_id, "deepseek", lease_seconds=60)
    assert running.state == RUNNING

    done = board.complete(
        task.task_id,
        "deepseek",
        evidence=["pytest tests/test_game.py -> 12 passed", "www/game.js"],
        files=["www/game.js"],
        test_command="pytest tests/test_game.py",
    )
    assert done.state == DONE
    assert done.evidence
    assert board.claim("codex") is None


def test_completion_requires_evidence(tmp_path) -> None:
    board = _board(tmp_path)
    task = board.enqueue("test")
    board.claim("a")

    with pytest.raises(ValueError):
        board.complete(task.task_id, "a", evidence=[])


def test_wrong_owner_cannot_finish(tmp_path) -> None:
    board = _board(tmp_path)
    task = board.enqueue("test")
    board.claim("a")

    with pytest.raises(TaskBoardError):
        board.complete(task.task_id, "b", evidence=["x"])
    with pytest.raises(TaskBoardError):
        board.fail(task.task_id, "b", "hata")


def test_lease_expiry_allows_reclaim(tmp_path) -> None:
    board = _board(tmp_path)
    task = board.enqueue("uzun iş")

    first = board.claim("slow-agent", lease_seconds=0.05)
    assert first is not None and first.owner == "slow-agent"
    time.sleep(0.1)

    second = board.claim("fast-agent")
    assert second is not None
    assert second.task_id == task.task_id
    assert second.owner == "fast-agent"
    assert second.attempts == 2


def test_live_lease_blocks_second_claim(tmp_path) -> None:
    board = _board(tmp_path)
    board.enqueue("iş")

    assert board.claim("a", lease_seconds=60) is not None
    assert board.claim("b") is None


def test_release_returns_task_to_queue(tmp_path) -> None:
    board = _board(tmp_path)
    task = board.enqueue("iş")
    board.claim("a")

    released = board.release(task.task_id, "a")

    assert released.state == QUEUED
    assert board.claim("b").task_id == task.task_id


def test_fail_records_reason_and_blocks_reclaim(tmp_path) -> None:
    board = _board(tmp_path)
    task = board.enqueue("iş")
    board.claim("a")

    failed = board.fail(task.task_id, "a", "bağımlılık yok")

    assert failed.state == BLOCKED
    assert "bağımlılık" in failed.reason
    assert board.claim("b") is None


def test_concurrent_claims_have_exactly_one_winner(tmp_path) -> None:
    board = _board(tmp_path)
    board.enqueue("tek iş")

    winners: list[str] = []
    barrier = threading.Barrier(4)

    def worker(name: str) -> None:
        local = TaskBoard(board.path)
        barrier.wait()
        claimed = local.claim(name, lease_seconds=60)
        if claimed is not None:
            winners.append(name)

    threads = [threading.Thread(target=worker, args=(f"agent-{i}",)) for i in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(winners) == 1, winners


def test_board_survives_reload(tmp_path) -> None:
    board = _board(tmp_path)
    task = board.enqueue("kalıcı iş")
    board.claim("a")

    reopened = TaskBoard(board.path)

    rows = reopened.tasks()
    assert [row.task_id for row in rows] == [task.task_id]
    assert rows[0].owner == "a"


def test_cli_add_claim_and_list(tmp_path, capsys) -> None:
    from ahos.taskboard import main

    board = str(tmp_path / "cli.json")

    assert main(["--board", board, "add", "CLI görevi"]) == 0
    assert "eklendi" in capsys.readouterr().out

    assert main(["--board", board, "claim", "agent-x"]) == 0
    assert "sahiplenildi" in capsys.readouterr().out

    assert main(["--board", board, "list"]) == 0
    listing = capsys.readouterr().out
    assert "claimed" in listing
    assert "agent-x" in listing


def test_cli_claim_returns_nonzero_when_empty(tmp_path, capsys) -> None:
    from ahos.taskboard import main

    code = main(["--board", str(tmp_path / "empty.json"), "claim", "a"])

    assert code == 1
    assert "uygun görev yok" in capsys.readouterr().out
