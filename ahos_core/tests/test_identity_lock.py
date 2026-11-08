"""Kimlik kilidi: 16 karakter, hash doğrulama, onaysız APPROVED engeli."""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import identity_lock  # noqa: E402


def test_lock_covers_16_and_verifies():
    lock = json.loads((ROOT / "studio" / "identity" / "identity-lock.json").read_text(encoding="utf-8"))
    assert lock["character_count"] == 16
    assert len({row["character_id"] for row in lock["characters"]}) == 16
    assert identity_lock.verify() == []


def test_no_character_is_approved_without_owner_record():
    lock = json.loads((ROOT / "studio" / "identity" / "identity-lock.json").read_text(encoding="utf-8"))
    for row in lock["characters"]:
        assert row["approval_status"] == "NONE"
        assert row["approved_by"] is None
        assert row["lock_status"] == "LOCKED_FOR_EDIT"


def test_tampering_is_detected(tmp_path, monkeypatch):
    chars = tmp_path / "characters"
    shutil.copytree(ROOT / "studio" / "characters", chars)
    monkeypatch.setattr(identity_lock, "CHARACTERS", chars)
    lock_path = tmp_path / "lock.json"
    rows = [identity_lock.character_record(cid) for cid in sorted(p.name for p in chars.iterdir())]
    payload = {"schema": "test", "character_count": 16,
               "characters": [{"character_id": row["character_id"], "identity_sha256": row["identity_sha256"],
                                "files": row["files"], "approval_status": "NONE"} for row in rows]}
    lock_path.write_text(json.dumps(payload), encoding="utf-8")
    assert identity_lock.verify(lock_path=lock_path, characters=chars) == []

    target = chars / "aden" / "character.json"
    data = json.loads(target.read_text(encoding="utf-8"))
    data["display_name"] = "Aden Değişti"
    target.write_text(json.dumps(data), encoding="utf-8")
    problems = identity_lock.verify(lock_path=lock_path, characters=chars)
    assert any("kimlik hash" in item for item in problems)


def test_change_bumps_version_and_resets_approval(tmp_path, monkeypatch):
    chars = tmp_path / "characters"
    chars.mkdir()
    shutil.copytree(ROOT / "studio" / "characters" / "aden", chars / "aden")
    monkeypatch.setattr(identity_lock, "CHARACTERS", chars)
    lock_path = tmp_path / "lock.json"
    record = identity_lock.character_record("aden")
    lock_path.write_text(json.dumps({"schema": "test", "character_count": 1, "characters": [
        {"character_id": "aden", "canon_version": "1.0.0", "lock_status": "LOCKED_FOR_EDIT",
         "approval_status": "APPROVED", "approved_by": "owner", "approved_at": "2026-11-01",
         "identity_sha256": record["identity_sha256"], "files": record["files"], "history": []}]}),
        encoding="utf-8")
    monkeypatch.setattr(identity_lock, "LOCK", lock_path)

    data = json.loads((chars / "aden" / "character.json").read_text(encoding="utf-8"))
    data["display_name"] = "Aden v2"
    (chars / "aden" / "character.json").write_text(json.dumps(data), encoding="utf-8")
    row = identity_lock.change("aden", "test değişikliği")

    assert row["canon_version"] == "1.1.0"
    assert row["approval_status"] == "NONE" and row["approved_by"] is None
    assert len(row["history"]) == 1
