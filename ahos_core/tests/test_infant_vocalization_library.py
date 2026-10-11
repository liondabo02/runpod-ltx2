import hashlib
import json
from pathlib import Path

import pytest

from ahos.infant_vocalization_library import (
    InfantVocalizationError, InfantVocalizationFactory, InfantVocalizationLibrary,
)


WAV = b"RIFF" + b"\0" * 4 + b"WAVE" + b"\0" * 64


def library(tmp_path: Path):
    asset = tmp_path / "runtime-artifacts" / "infants" / "ramin" / "coo.wav"
    asset.parent.mkdir(parents=True)
    asset.write_bytes(WAV)
    manifest = tmp_path / "artifacts" / "infant-vocalizations.json"
    manifest.parent.mkdir()
    manifest.write_text(json.dumps({
        "schema": "ahos.infant-vocalization-library.v1",
        "characters": {"ramin": {"age_months": 1, "assets": {"coo": {
            "path": asset.relative_to(tmp_path).as_posix(),
            "sha256": hashlib.sha256(WAV).hexdigest(),
        }}}},
    }), encoding="utf-8")
    return InfantVocalizationLibrary(tmp_path), asset


def test_selects_and_materializes_hash_locked_nonverbal_asset(tmp_path):
    store, _ = library(tmp_path)
    selected = store.select("ramin", "coo")
    target = tmp_path / "runtime-artifacts" / "tts" / "unit.wav"
    store.materialize("ramin", "coo", target)
    assert selected.character_id == "ramin"
    assert target.read_bytes() == WAV


def test_rejects_tampering_and_unknown_cues(tmp_path):
    store, asset = library(tmp_path)
    asset.write_bytes(WAV + b"changed")
    with pytest.raises(InfantVocalizationError, match="missing or changed"):
        store.select("ramin", "coo")
    with pytest.raises(InfantVocalizationError, match="unsupported"):
        store.select("ramin", "sentence")


class FakeDesignProvider:
    provider_id = "fake-design"

    def __init__(self):
        self.calls = []

    def design(self, **kwargs):
        self.calls.append(kwargs)
        return WAV


def test_factory_generates_distinct_complete_resumable_infant_library(tmp_path):
    provider = FakeDesignProvider()
    factory = InfantVocalizationFactory(tmp_path)
    first = factory.generate(provider)
    assert first["complete"] is True
    assert len(provider.calls) == 10
    assert all(call["text"] == "Mm... ah... ooh..." for call in provider.calls)
    assert all("No words" in call["instruct"] for call in provider.calls)
    second = factory.generate(provider)
    assert second["complete"] is True
    assert len(provider.calls) == 10
