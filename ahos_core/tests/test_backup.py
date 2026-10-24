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
