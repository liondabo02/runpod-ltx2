"""Outbox-backed produce step: real files, real gate, stop file respected."""

from __future__ import annotations

import json

from ahos.outbox_executor import make_outbox_executor


def _project(tmp_path):
    root = tmp_path / "proj"
    (root / "www").mkdir(parents=True)
    (root / "www" / "app.js").write_text("const hello = 'Hello';\n", encoding="utf-8")
    (root / "tools").mkdir()
    (root / "tools" / "check_offline.py").write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
    return root


def _proposal(tmp_path, root, *, find="'Hello'", replace="'Merhaba'", task="selamla"):
    outbox = tmp_path / "outbox"
    outbox.mkdir(exist_ok=True)
    (outbox / "p1.json").write_text(
        json.dumps(
            {
                "id": "p1",
                "task": task,
                "edits": [{"path": "www/app.js", "find": find, "replace": replace}],
            }
        ),
        encoding="utf-8",
    )
    return outbox


class _Item:
    def __init__(self, task_id: str, title: str) -> None:
        self.task_id = task_id
        self.title = title


def test_proposal_is_applied_and_archived(tmp_path) -> None:
    root = _project(tmp_path)
    outbox = _proposal(tmp_path, root)
    executor = make_outbox_executor(root, outbox)

    result = executor(_Item("oyun:m1:produce", "selamla"), "w1")

    assert result.success is True
    assert "'Merhaba'" in (root / "www" / "app.js").read_text(encoding="utf-8")
    assert (outbox / "p1.json").exists() is False
    assert (outbox / "applied" / "p1.json").exists()


def test_no_proposal_means_no_delivery(tmp_path) -> None:
    root = _project(tmp_path)
    outbox = tmp_path / "outbox"
    outbox.mkdir()
    executor = make_outbox_executor(root, outbox)

    result = executor(_Item("oyun:m1:produce", "selamla"), "w1")

    assert result.success is False
    assert "uygun öneri yok" in result.summary


def test_bad_patch_is_rejected_without_touching_the_file(tmp_path) -> None:
    root = _project(tmp_path)
    outbox = _proposal(tmp_path, root, find="yok")
    executor = make_outbox_executor(root, outbox)

    result = executor(_Item("oyun:m1:produce", "selamla"), "w1")

    assert result.success is False
    assert "'Hello'" in (root / "www" / "app.js").read_text(encoding="utf-8")


def test_stop_file_blocks_application(tmp_path) -> None:
    root = _project(tmp_path)
    outbox = _proposal(tmp_path, root)
    stop = tmp_path / "autonomy.stop"
    stop.write_text("dur", encoding="utf-8")
    executor = make_outbox_executor(root, outbox, stop_file=stop)

    result = executor(_Item("oyun:m1:produce", "selamla"), "w1")

    assert result.success is False
    assert "acil durdurma" in result.summary
    assert "'Hello'" in (root / "www" / "app.js").read_text(encoding="utf-8")
