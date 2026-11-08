from __future__ import annotations

import json

from ahos.errors import ErrorLog, default_error_log


def test_record_and_read_back(tmp_path) -> None:
    log = ErrorLog(tmp_path / "errors.jsonl")

    log.record("panel", RuntimeError("boom"), mission_id="m-1", context={"port": 8766})
    log.record("daemon", ValueError("bad config"))

    rows = log.recent(10)
    assert len(rows) == 2
    assert rows[0]["kind"] == "RuntimeError"
    assert rows[0]["message"] == "boom"
    assert rows[0]["mission_id"] == "m-1"
    assert rows[0]["context"] == {"port": "8766"}
    assert rows[1]["source"] == "daemon"
    assert log.count() == 2


def test_traceback_is_captured_and_bounded(tmp_path) -> None:
    log = ErrorLog(tmp_path / "errors.jsonl")
    try:
        raise RuntimeError("x" * 50)
    except RuntimeError as exc:
        record = log.record("worker", exc)

    assert "traceback" in record
    assert "RuntimeError" in record["traceback"]
    assert len(record["traceback"]) <= 4000


def test_long_message_is_truncated(tmp_path) -> None:
    log = ErrorLog(tmp_path / "errors.jsonl")
    record = log.record("x", "y" * 5000)

    assert len(record["message"]) == 1000


def test_file_rotates_at_size_limit(tmp_path) -> None:
    path = tmp_path / "errors.jsonl"
    log = ErrorLog(path, max_bytes=200)

    for _ in range(5):
        log.record("x", "message that takes some space")

    backup = path.with_suffix(".jsonl.1")
    assert backup.exists(), "boyut sınırında yedek dosya oluşmalı"
    assert log.count() >= 1


def test_recent_tolerates_corrupt_lines(tmp_path) -> None:
    path = tmp_path / "errors.jsonl"
    path.write_text(
        json.dumps({"source": "ok", "kind": "Error", "message": "fine"})
        + "\n"
        + "{not json\n",
        encoding="utf-8",
    )

    rows = ErrorLog(path).recent(10)

    assert [row["source"] for row in rows] == ["ok"]


def test_cli_prints_recent_errors(tmp_path, capsys) -> None:
    from ahos.errors import main

    log = default_error_log(tmp_path)
    log.record("daemon", "disk full", mission_id="m-9")

    assert main(["--runtime-dir", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "daemon" in out
    assert "disk full" in out
    assert "m-9" in out


def test_cli_with_no_errors(tmp_path, capsys) -> None:
    from ahos.errors import main

    assert main(["--runtime-dir", str(tmp_path)]) == 0
    assert "hata kaydı yok" in capsys.readouterr().out
