from __future__ import annotations

import json

from ahos.adapters.ruflo_bridge import (
    queue_dir,
    read_result,
    results_dir,
    submit,
    wait_for_result,
)


def test_submit_writes_request_file(tmp_path) -> None:
    path = submit(
        tmp_path,
        mission_id="m-1:produce",
        prompt="karta yorum ekle",
        project=str(tmp_path / "proj"),
        timeout_seconds=60,
    )

    assert path.exists()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["mission_id"] == "m-1:produce"
    assert payload["prompt"] == "karta yorum ekle"
    assert path.parent == queue_dir(tmp_path)


def test_result_roundtrip(tmp_path) -> None:
    results_dir(tmp_path).mkdir(parents=True, exist_ok=True)
    target = results_dir(tmp_path) / "m-1_produce.json"
    target.write_text(
        json.dumps({"status": "completed", "exit_code": 0}), encoding="utf-8"
    )

    assert read_result(tmp_path, "m-1:produce")["status"] == "completed"


def test_missing_result_returns_none(tmp_path) -> None:
    assert read_result(tmp_path, "yok") is None


def test_wait_times_out_without_result(tmp_path) -> None:
    slept: list[float] = []

    result = wait_for_result(
        tmp_path,
        "m-x",
        timeout_seconds=0.05,
        poll_seconds=0.01,
        sleep=slept.append,
        clock=lambda: 0.0,
    )

    assert result is None


def test_wait_returns_result_when_written(tmp_path) -> None:
    results_dir(tmp_path).mkdir(parents=True, exist_ok=True)
    (results_dir(tmp_path) / "m-y.json").write_text(
        json.dumps({"status": "completed"}), encoding="utf-8"
    )

    result = wait_for_result(tmp_path, "m-y", timeout_seconds=5, sleep=lambda _: None)

    assert result is not None
    assert result["status"] == "completed"
