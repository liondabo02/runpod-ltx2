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


def test_expired_owner_cannot_modify_or_extend_task(tmp_path) -> None:
    board = _board(tmp_path)
    task = board.enqueue("expired")
    board.claim("codex", lease_seconds=0.01)
    time.sleep(0.04)

    with pytest.raises(TaskBoardError, match="süresi dolmuş"):
        board.heartbeat(task.task_id, "codex")
    with pytest.raises(TaskBoardError, match="süresi dolmuş"):
        board.complete(task.task_id, "codex", evidence=["test"])
    with pytest.raises(TaskBoardError, match="süresi dolmuş"):
        board.handoff(task.task_id, "codex", "deepseek")

    reclaimed = board.claim("deepseek")
    assert reclaimed is not None and reclaimed.owner == "deepseek"
    assert reclaimed.attempts == 2
    with pytest.raises(TaskBoardError, match="başka sahipte"):
        board.release(task.task_id, "codex")


def test_handoff_owner_audit_and_completion(tmp_path) -> None:
    board = _board(tmp_path)
    task = board.enqueue("CEO -> kodlama")
    board.claim("ceo")
    transferred = board.handoff(task.task_id, "ceo", "codex", lease_seconds=60)
    assert transferred.owner == "codex"
    assert transferred.attempts == 2

    with pytest.raises(TaskBoardError, match="başka sahipte"):
        board.complete(task.task_id, "ceo", evidence=["not my work"])

    board.heartbeat(task.task_id, "codex")
    finished = board.complete(task.task_id, "codex", evidence=["tests passed"])
    assert [event["action"] for event in finished.history] == [
        "created", "claimed", "handed_off", "started", "completed"
    ]
    assert finished.history[2]["previous_owner"] == "ceo"
    assert finished.history[2]["actor"] == "codex"


def test_dedupe_key_prevents_duplicate_active_jobs(tmp_path) -> None:
    board = _board(tmp_path)
    first = board.enqueue("task one", dedupe_key=" MIPILUNA-42 ")
    same = board.enqueue("same work again", dedupe_key="mipiluna-42")
    assert first.task_id == same.task_id
    assert len(board.tasks()) == 1
    board.claim("codex")
    board.complete(first.task_id, "codex", evidence=["done"])
    later = board.enqueue("new cycle", dedupe_key="mipiluna-42")
    assert later.task_id != first.task_id


def test_corrupt_board_fails_closed_without_data_loss(tmp_path) -> None:
    path = tmp_path / "tasks.json"
    path.write_text('{"tasks": [', encoding="utf-8")
    board = TaskBoard(path)
    with pytest.raises(TaskBoardError, match="korunuyor"):
        board.tasks()
    with pytest.raises(TaskBoardError, match="korunuyor"):
        board.enqueue("unsafe overwrite")
    assert path.read_text(encoding="utf-8") == '{"tasks": ['


def test_read_does_not_rewrite_file(tmp_path) -> None:
    board = _board(tmp_path)
    task = board.enqueue("read only")
    original = board.path.read_bytes()
    assert board.get(task.task_id) is not None
    assert board.tasks()
    assert board.path.read_bytes() == original


@pytest.mark.parametrize("invalid", [0, -1, float("inf"), float("nan")])
def test_reject_invalid_leases(tmp_path, invalid) -> None:
    board = _board(tmp_path)
    task = board.enqueue("lease")
    with pytest.raises(ValueError):
        board.claim("codex", lease_seconds=invalid)
    board.claim("codex")
    with pytest.raises(ValueError):
        board.heartbeat(task.task_id, "codex", lease_seconds=invalid)
    with pytest.raises(ValueError):
        board.handoff(task.task_id, "codex", "deepseek", lease_seconds=invalid)


def test_cli_handoff_and_history(tmp_path, capsys) -> None:
    from ahos.taskboard import main
    board = str(tmp_path / "cli.json")
    assert main(["--board", board, "add", "work", "--key", "work-123"]) == 0
    task_id = TaskBoard(board).tasks()[0].task_id
    capsys.readouterr()
    assert main(["--board", board, "claim", "codex"]) == 0
    assert main(["--board", board, "handoff", task_id, "codex", "deepseek"]) == 0
    assert main(["--board", board, "heartbeat", task_id, "deepseek"]) == 0
    assert main(["--board", board, "history", task_id]) == 0
    output = capsys.readouterr().out
    assert '"handed_off"' in output
    assert '"deepseek"' in output
    assert main(["--board", board, "release", task_id, "deepseek"]) == 0
    assert TaskBoard(board).get(task_id).state == QUEUED


def test_specific_claim_does_not_steal_an_unrelated_task(tmp_path) -> None:
    board = _board(tmp_path)
    board.enqueue("unrelated", task_id="unrelated")
    task = board.claim_task("mission:build", "build", "runner-one")
    assert task is not None and task.owner == "runner-one"
    assert board.get("unrelated").state == QUEUED
    assert board.claim_task("mission:build", "build", "runner-two") is None
    board.heartbeat(task.task_id, "runner-one")
    board.complete(task.task_id, "runner-one", evidence=["QA verified"])
    assert board.claim_task("mission:build", "build", "runner-three") is None
