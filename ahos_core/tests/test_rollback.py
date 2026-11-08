"""Rollback snapshots and restores use isolated pytest directories."""
import pytest
from ahos import rollback


def test_snapshot_copies_files(tmp_path, monkeypatch):
    monkeypatch.setattr(rollback, "ARTIFACTS_ROOT", tmp_path / "artifacts")
    source = tmp_path / "project"
    source.mkdir()
    (source / "original.txt").write_text("rollback test content", encoding="utf-8")
    snap = rollback.snapshot(source, ["original.txt"])
    assert snap.is_dir()
    assert (snap / "original.txt").read_text(encoding="utf-8") == "rollback test content"


def test_restore_restores_content(tmp_path, monkeypatch):
    monkeypatch.setattr(rollback, "ARTIFACTS_ROOT", tmp_path / "artifacts")
    source = tmp_path / "project"
    source.mkdir()
    target = source / "change.txt"
    target.write_text("original content", encoding="utf-8")
    snap = rollback.snapshot(source, ["change.txt"])
    target.write_text("modified content", encoding="utf-8")
    assert rollback.restore(snap, source) == 1
    assert target.read_text(encoding="utf-8") == "original content"


def test_last_finds_newest_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(rollback, "ARTIFACTS_ROOT", tmp_path / "artifacts")
    project = tmp_path / "project"
    project.mkdir()
    (project / "file.txt").write_text("x", encoding="utf-8")
    earlier = rollback.snapshot(project, ["file.txt"])
    newest = rollback.snapshot(project, ["file.txt"])
    assert earlier != newest
    assert newest.name.startswith("20")
    assert rollback.last() == newest


def test_snapshot_rejects_parent_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr(rollback, "ARTIFACTS_ROOT", tmp_path / "artifacts")
    project = tmp_path / "project"
    project.mkdir()
    (tmp_path / "secret.txt").write_text("do not copy", encoding="utf-8")
    with pytest.raises(ValueError):
        rollback.snapshot(project, ["../secret.txt"])
