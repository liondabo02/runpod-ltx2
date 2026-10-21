from __future__ import annotations

import json

from ahos.errors import default_error_log
from ahos.report import collect, render
from ahos.taskboard import TaskBoard


def _runtime(tmp_path):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (runtime / "daemon-state.json").write_text(
        json.dumps(
            {
                "pid": 4242,
                "ticks": 9,
                "status": "running",
                "executor_mode": "deterministic",
                "executor_reason": "model yapılandırılmadı",
                "no_evidence_streak": 1,
            }
        ),
        encoding="utf-8",
    )
    (runtime / "autonomy-state.json").write_text(
        json.dumps({"status": "idle", "executed": 3, "failed": 1}),
        encoding="utf-8",
    )
    (runtime / "auto-scheduler-state.json").write_text(
        json.dumps(
            {"missions_this_hour": 2, "missions_total": 7, "status": "quota_wait"}
        ),
        encoding="utf-8",
    )
    ledger = [
        {"mission_id": "m-1", "changed_files": 2, "evidence_ok": True},
        {"mission_id": "m-2", "changed_files": 0, "evidence_ok": False},
    ]
    (runtime / "daemon-missions.jsonl").write_text(
        "\n".join(json.dumps(row) for row in ledger) + "\n", encoding="utf-8"
    )
    default_error_log(runtime).record("daemon.tick", "patlama")
    board = TaskBoard(runtime / "taskboard.json")
    board.enqueue("açık iş")
    return runtime


def test_empty_runtime_reports_not_running(tmp_path) -> None:
    runtime = tmp_path / "empty"
    runtime.mkdir()

    report = collect(runtime)

    assert report["daemon"]["running"] is False
    assert report["delivery"]["recorded"] == 0
    assert "not-running" in render(report)


def test_collect_merges_every_ledger(tmp_path) -> None:
    runtime = _runtime(tmp_path)

    report = collect(runtime)

    assert report["daemon"]["pid"] == 4242
    assert report["daemon"]["executor_mode"] == "deterministic"
    assert report["scheduler"]["missions_total"] == 7
    assert report["delivery"]["recorded"] == 2
    assert report["delivery"]["with_changes"] == 1
    assert report["errors"][0]["source"] == "daemon.tick"
    assert report["board"]["open"] == 1


def test_render_marks_deliveries_and_errors(tmp_path) -> None:
    runtime = _runtime(tmp_path)

    text = render(collect(runtime))

    assert "pid 4242" in text
    assert "1/2 görevde dosya değişikliği" in text
    assert "✓" in text
    assert "daemon.tick" in text


def test_json_cli_output(tmp_path, capsys) -> None:
    from ahos.report import main

    runtime = _runtime(tmp_path)
    assert main(["--runtime-dir", str(runtime), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["daemon"]["ticks"] == 9


def test_text_cli_output(tmp_path, capsys) -> None:
    from ahos.report import main

    runtime = _runtime(tmp_path)
    assert main(["--runtime-dir", str(runtime)]) == 0
    assert "AHOS DURUM" in capsys.readouterr().out
