"""Prove AHOS release preflight fails closed and never deploys anything."""

from __future__ import annotations

import json
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from ahos.backup import backup
from ahos.release_gate import check_readiness, main


def _make_queue(runtime: Path, *, blocked: int, completed: int) -> None:
    with sqlite3.connect(runtime / "company-service.db") as con:
        con.execute("CREATE TABLE missions (status TEXT)")
        con.executemany("INSERT INTO missions VALUES (?)", [
            ("completed",) for _ in range(completed)
        ] + [("blocked",) for _ in range(blocked)])


def _ready_runtime(tmp_path: Path) -> tuple[Path, Path]:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    repo = tmp_path / "repo"
    repo.mkdir()

    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
    (repo / "README.md").write_text("verified workspace\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "README.md"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "test baseline"], check=True)
    rev = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], check=True,
                         capture_output=True, text=True).stdout.strip()

    now = datetime.now(timezone.utc).isoformat()
    (runtime / "daemon-state.json").write_text(json.dumps({
        "status": "running", "last_tick_at": now, "quality": {
            "delivery_rate": 0.96, "missions": 100,
        }, "last_evidence": {
            "evidence_ok": True, "changed_files": 2,
        },
    }), encoding="utf-8")

    _make_queue(runtime, blocked=1, completed=99)
    with sqlite3.connect(runtime / "owner-approvals.db") as con:
        con.execute("CREATE TABLE approvals (id INTEGER PRIMARY KEY)")

    for name in ("worker-metrics.jsonl", "audit.jsonl", "taskboard.json"):
        (runtime / name).write_text("{}\n", encoding="utf-8")
    (runtime / "release-test-receipt.json").write_text(json.dumps({
        "commit_sha": rev, "exit_code": 0, "passed": 100,
        "failed": 0, "trusted_ci": True,
    }), encoding="utf-8")
    backup(runtime)
    return runtime, repo


def test_missing_runtime_fails_closed(tmp_path: Path) -> None:
    checks = check_readiness(tmp_path / "missing", tmp_path / "unknown")
    assert checks and all(not item.ok for item in checks)
    assert main(["--runtime-dir", str(tmp_path / "missing"),
                 "--repository", str(tmp_path / "unknown")]) == 2


def test_completed_gates_allow_owner_review_not_deploy(tmp_path: Path) -> None:
    runtime, repo = _ready_runtime(tmp_path)
    checks = check_readiness(runtime, repo)
    assert all(item.ok for item in checks), checks
    assert main(["--runtime-dir", str(runtime), "--repository", str(repo)]) == 0


def test_low_delivery_rate_blocks_release(tmp_path: Path) -> None:
    runtime, repo = _ready_runtime(tmp_path)
    state = runtime / "daemon-state.json"
    data = json.loads(state.read_text(encoding="utf-8"))
    data["quality"]["delivery_rate"] = 0.065
    state.write_text(json.dumps(data), encoding="utf-8")
    checks = check_readiness(runtime, repo)
    assert next(x for x in checks if x.name == "delivery_quality").ok is False


def test_uncommitted_code_blocks_release(tmp_path: Path) -> None:
    runtime, repo = _ready_runtime(tmp_path)
    (repo / "unreviewed.py").write_text("print('not reviewed')\n", encoding="utf-8")
    assert next(x for x in check_readiness(runtime, repo)
                if x.name == "clean_source_tree").ok is False


def test_missing_trusted_receipt_blocks_release(tmp_path: Path) -> None:
    runtime, repo = _ready_runtime(tmp_path)
    (runtime / "release-test-receipt.json").unlink()
    assert next(x for x in check_readiness(runtime, repo)
                if x.name == "trusted_test_receipt").ok is False


def test_unverified_old_backup_blocks_release(tmp_path: Path) -> None:
    runtime, repo = _ready_runtime(tmp_path)
    archive = next((runtime / "backups").glob("runtime-*.zip"))
    archive.write_bytes(b"old corrupt archive")
    assert next(x for x in check_readiness(runtime, repo)
                if x.name == "verified_backup").ok is False
