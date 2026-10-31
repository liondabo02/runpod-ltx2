"""Runtime backups: state is copied, never deleted."""

from __future__ import annotations

import json
import zipfile

from ahos.backup import backup


def test_backup_captures_state_and_knowledge(tmp_path) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (runtime / "daemon-state.json").write_text(json.dumps({"pid": 1}), encoding="utf-8")
    (runtime / "knowledge").mkdir()
    (runtime / "knowledge" / "lessons.jsonl").write_text(
        json.dumps({"lesson": "test kapısı"}) + "\n", encoding="utf-8"
    )

    archive = backup(runtime)

    assert archive is not None and archive.is_file()
    with zipfile.ZipFile(archive) as bundle:
        names = bundle.namelist()
    assert any("daemon-state.json" in name for name in names)
    assert any("lessons.jsonl" in name for name in names)


def test_old_archives_are_kept_as_old(tmp_path) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (runtime / "daemon-state.json").write_text("{}", encoding="utf-8")
    backups = runtime / "backups"
    backups.mkdir()
    for index in range(9):
        (backups / f"runtime-2000010{index}-0000.zip").write_bytes(b"old")

    backup(runtime)

    assert (backups / "runtime-20000100-0000.zip.old").exists()
    assert len(list(backups.glob("runtime-*.zip"))) == 7


def test_backup_preserves_committed_wal_rows(tmp_path) -> None:
    """A plain copy of the main SQLite file can omit recently committed WAL rows."""
    import sqlite3

    runtime = tmp_path / "runtime"
    runtime.mkdir()
    db = runtime / "company-service.db"
    connection = sqlite3.connect(db)
    try:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("CREATE TABLE records (value TEXT)")
        connection.commit()
        connection.execute("INSERT INTO records VALUES ('wal-committed')")
        connection.commit()
        assert (runtime / "company-service.db-wal").exists()

        archive = backup(runtime)
        with zipfile.ZipFile(archive) as bundle:
            payload = bundle.read("runtime/company-service.db")
        restored = sqlite3.connect(":memory:")
        try:
            restored.deserialize(payload)
            assert restored.execute("SELECT value FROM records").fetchone()[0] == "wal-committed"
        finally:
            restored.close()
    finally:
        connection.close()


def test_backup_includes_state_and_excludes_secrets(tmp_path) -> None:
    from ahos.backup import verify_archive

    runtime = tmp_path / "runtime"
    runtime.mkdir()
    for name in ("worker-metrics.jsonl", "audit.jsonl", "taskboard.json", "live-events.jsonl"):
        (runtime / name).write_text('{"safe":true}\n', encoding="utf-8")
    (runtime / "ceo").mkdir()
    (runtime / "ceo" / "decisions.jsonl").write_text('{"approved":true}\n', encoding="utf-8")
    (runtime / "knowledge").mkdir()
    (runtime / "knowledge" / "secret-api-key.txt").write_text("do-not-archive", encoding="utf-8")
    (runtime / ".env").write_text("DO_NOT_ARCHIVE=1", encoding="utf-8")

    archive = backup(runtime)
    report = verify_archive(archive)
    assert report["schema"] == "ahos.runtime-backup.v2"
    with zipfile.ZipFile(archive) as bundle:
        names = set(bundle.namelist())
        for name in ("worker-metrics.jsonl", "audit.jsonl", "taskboard.json", "live-events.jsonl",
                     "ceo/decisions.jsonl"):
            assert f"runtime/{name}" in names
        assert not any(".env" in name or "secret" in name for name in names)


def test_backup_names_are_unique_in_same_second(tmp_path, monkeypatch) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (runtime / "daemon-state.json").write_text("{}", encoding="utf-8")
    first = backup(runtime)
    second = backup(runtime)
    assert first != second
    assert first.exists() and second.exists()


def test_backup_digest_verification_catches_tampering(tmp_path) -> None:
    from ahos.backup import verify_archive
    import pytest

    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (runtime / "daemon-state.json").write_text("{}", encoding="utf-8")
    archive = backup(runtime)
    # Rebuild an otherwise valid ZIP but tamper with one payload, leaving the manifest unchanged.
    with zipfile.ZipFile(archive) as original:
        content = {name: original.read(name) for name in original.namelist()}
    content["runtime/daemon-state.json"] = b'{"tampered":true}'
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as changed:
        for name, data in content.items():
            changed.writestr(name, data)
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        verify_archive(archive)
