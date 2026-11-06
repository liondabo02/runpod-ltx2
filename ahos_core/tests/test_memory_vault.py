"""Safe memory-vault integrity, online backup, and no-destructive-restore tests."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from zipfile import ZipFile

import pytest

from ahos.memory_vault import (
    audit_worker_minds, snapshot, snapshot_if_due, verify,
)


def _runtime(tmp_path, *, workers=4):
    rt = tmp_path / "ahos_core" / "runtime"
    rt.mkdir(parents=True)
    db = sqlite3.connect(rt / "company-service.db")
    try:
        db.execute("create table missions (mission_id text primary key, status text)")
        db.executemany("insert into missions values (?,?)",
                       [(f"m-{i}", "completed") for i in range(4)])
        db.commit()
    finally:
        db.close()
    dep = {
        "departments": [{"department_id": "software",
                         "workers": [{"worker_id": f"worker-{i}"} for i in range(workers)]}]
    }
    (rt / "departments.json").write_text(json.dumps(dep), encoding="utf-8")
    (rt / "minds").mkdir()
    for i in range(workers):
        (rt / "minds" / f"worker-{i}.json").write_text(
            json.dumps({"worker_id": f"worker-{i}", "self_model": {"events": [i]}}),
            encoding="utf-8",
        )
    (rt / "minds" / "conversations.jsonl").write_text(
        '{"mission_id":"m-1","text":"conversation"}\n', encoding="utf-8",
    )
    (rt / "learning").mkdir()
    (rt / "learning" / "software.jsonl").write_text(
        '{"worker":"worker-0","learned":true}\n', encoding="utf-8",
    )
    (rt / "model.env").write_text("FAKE_API_KEY=private", encoding="utf-8")
    (rt / "minds" / "secret_token.json").write_text(
        '{"secret":"must not be archived"}', encoding="utf-8",
    )
    return rt


def test_online_sqlite_snapshot_preserves_memory_and_verifies_every_hash(tmp_path):
    rt = _runtime(tmp_path)
    backup = tmp_path / "safe_snapshots"
    before = (rt / "minds" / "worker-2.json").read_bytes()
    result = snapshot(rt, backup)
    assert result["verified"] is True
    assert result["files"] >= 7
    sealed = Path(result["snapshot"])
    assert verify(sealed)["verified"] is True
    with sqlite3.connect(sealed / "company-service.db") as db:
        assert db.execute("select count(*) from missions").fetchone()[0] == 4
    with ZipFile(sealed / "memories.zip") as archive:
        names = archive.namelist()
        assert "minds/worker-2.json" in names
        assert archive.read("minds/worker-2.json") == before
        assert "model.env" not in names
        assert "minds/secret_token.json" not in names
    assert (rt / "minds" / "worker-2.json").read_bytes() == before


def test_hash_tampering_is_detected_and_original_source_is_untouched(tmp_path):
    rt = _runtime(tmp_path)
    result = snapshot(rt, tmp_path / "backup")
    path = Path(result["snapshot"]) / "memories.zip"
    original = (rt / "minds" / "worker-0.json").read_bytes()
    path.write_bytes(path.read_bytes() + b"corrupted-data")
    with pytest.raises(ValueError, match="corrupted"):
        verify(path.parent)
    assert (rt / "minds" / "worker-0.json").read_bytes() == original


def test_due_snapshots_are_bounded_and_never_delete_older_backups(tmp_path):
    rt = _runtime(tmp_path)
    root = tmp_path / "backups"
    first = snapshot_if_due(rt, root, every_seconds=600, now=1000)
    assert first["status"] == "saved"
    second = snapshot_if_due(rt, root, every_seconds=600, now=1200)
    assert second["status"] == "fresh"
    third = snapshot_if_due(rt, root, every_seconds=600, now=1700)
    assert third["status"] == "saved"
    assert Path(first["snapshot"]).exists()
    assert Path(third["snapshot"]).exists()
    assert len(list(root.glob("vault-*/manifest.json"))) == 2


def test_worker_integrity_auditor_catches_missing_and_corrupt_files(tmp_path):
    rt = _runtime(tmp_path)
    audit = audit_worker_minds(rt)
    assert audit == {"ok": True, "rostered": 4, "missing": [], "invalid": []}
    (rt / "minds" / "worker-0.json").unlink()
    corrupted = rt / "minds" / "worker-1.json"
    corrupted.write_bytes(b"unparseable")
    audit = audit_worker_minds(rt)
    assert audit["ok"] is False
    assert audit["missing"] == ["worker-0"]
    assert audit["invalid"] == ["worker-1"]
    assert corrupted.read_bytes() == b"unparseable"


def test_missing_database_never_generates_a_fake_backup(tmp_path):
    rt = _runtime(tmp_path)
    (rt / "company-service.db").unlink()
    root = tmp_path / "backups"
    with pytest.raises(FileNotFoundError):
        snapshot(rt, root)
    assert not list(root.glob("vault-*"))


def test_existing_backup_never_overwrites_or_restores_live_source(tmp_path):
    rt = _runtime(tmp_path)
    root = tmp_path / "backups"
    one = snapshot(rt, root)
    before = (rt / "minds" / "worker-0.json").read_bytes()
    two = snapshot(rt, root)
    assert one["snapshot"] != two["snapshot"]
    assert verify(one["snapshot"])["verified"]
    assert verify(two["snapshot"])["verified"]
    assert (rt / "minds" / "worker-0.json").read_bytes() == before


def test_backup_root_inside_runtime_is_rejected(tmp_path):
    rt = _runtime(tmp_path)
    with pytest.raises(ValueError, match="separate"):
        snapshot(rt, rt / "backups")


def test_corrupted_recent_backup_never_counts_as_fresh(tmp_path):
    rt = _runtime(tmp_path)
    root = tmp_path / "backup"
    first = snapshot_if_due(rt, root, every_seconds=600, now=1000)
    corrupted = Path(first["snapshot"]) / "memories.zip"
    corrupted.write_bytes(corrupted.read_bytes() + b"tampering")
    second = snapshot_if_due(rt, root, every_seconds=600, now=1100)
    assert second["status"] == "saved"
    assert second["snapshot"] != first["snapshot"]
    assert Path(first["snapshot"]).exists()
    assert verify(second["snapshot"])["verified"]


def test_daemon_vault_hook_exposes_verified_backup_and_worker_integrity(tmp_path, monkeypatch):
    from ahos.daemon import _memory_vault_report
    from ahos import memory_vault

    monkeypatch.setattr(memory_vault, "default_backup_root",
                        lambda runtime: tmp_path / "AHOS_BACKUPS")
    rt = _runtime(tmp_path, workers=5)
    first = _memory_vault_report(rt)
    assert first["status"] == "saved"
    assert first["verified"] is True
    assert first["roster_integrity"]["ok"] is True
    assert first["roster_integrity"]["rostered"] == 5

    second = _memory_vault_report(rt)
    assert second["status"] == "fresh"
    assert second["verified"] is True
    assert len(list((tmp_path / "AHOS_BACKUPS").glob("vault-*/manifest.json"))) == 1


def test_locked_backup_is_preserved_not_bypassed(tmp_path):
    rt = _runtime(tmp_path)
    root = tmp_path / "backups"
    root.mkdir()
    lock = root / ".memory-vault.lock"
    lock.write_text("other process", encoding="utf-8")
    report = snapshot_if_due(rt, root)
    assert report["status"] == "locked"
    assert lock.read_text(encoding="utf-8") == "other process"
    assert not list(root.glob("vault-*"))


def test_source_symlink_does_not_escape_runtime_archive(tmp_path):
    rt = _runtime(tmp_path)
    secret = tmp_path / "external.txt"
    secret.write_text("PRIVATE MATERIAL OUTSIDE AHOS", encoding="utf-8")
    link = rt / "minds" / "innocent.txt"
    try:
        link.symlink_to(secret)
    except (OSError, NotImplementedError):
        pytest.skip("test user cannot create file symlinks")
    result = snapshot(rt, tmp_path / "out")
    with ZipFile(Path(result["snapshot"]) / "memories.zip") as archive:
        assert "minds/innocent.txt" not in archive.namelist()


def test_invalid_worker_id_cannot_escape_runtime_during_integrity_audit(tmp_path):
    rt = _runtime(tmp_path, workers=0)
    book = {"departments": [{"department_id": "software", "workers": [
        {"worker_id": "../../external"},
    ]}]}
    (rt / "departments.json").write_text(json.dumps(book), encoding="utf-8")
    report = audit_worker_minds(rt)
    assert report["ok"] is False
    assert report["invalid"] == ["../../external"]
