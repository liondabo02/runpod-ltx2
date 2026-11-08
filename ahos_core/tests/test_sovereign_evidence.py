"""Owner pledge behavior must be fail-closed and truthful."""
from __future__ import annotations

import json

import pytest

from ahos import sovereign


def test_default_owner_matches_existing_production_identity(tmp_path, monkeypatch):
    monkeypatch.delenv("AHOS_OWNER", raising=False)
    assert sovereign.owner() == "harun"
    record = sovereign.ensure(tmp_path)
    assert record["owner"] == "harun"
    assert sovereign.is_commander("harun")
    assert not sovereign.is_commander("esmak")


def test_existing_owner_pledge_never_changes_on_env_override(tmp_path, monkeypatch):
    monkeypatch.delenv("AHOS_OWNER", raising=False)
    record = sovereign.ensure(tmp_path)
    monkeypatch.setenv("AHOS_OWNER", "different")
    same = sovereign.ensure(tmp_path)
    assert same == record
    assert json.loads((tmp_path / "minds" / "_pledge.json").read_text(encoding="utf-8")) == record


def test_corrupted_pledge_is_preserved_and_rejected(tmp_path, monkeypatch):
    monkeypatch.delenv("AHOS_OWNER", raising=False)
    sovereign.ensure(tmp_path)
    path = tmp_path / "minds" / "_pledge.json"
    original = b'{"owner":"other","hash":"invalid"}'
    path.write_bytes(original)
    with pytest.raises(ValueError, match="hash mismatch"):
        sovereign.ensure(tmp_path)
    assert path.read_bytes() == original
