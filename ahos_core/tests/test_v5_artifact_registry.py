"""V5 GÖREV 022: teslimat kayıt defteri dosya/QA ayrımını korur."""
from __future__ import annotations

import hashlib
import json

import pytest

from ahos import artifact_registry


def _manifest(tmp_path, qa_ok=True, fake_hash=False):
    video = tmp_path / "out.mp4"
    video.write_bytes(b"real-video-bytes")
    digest = hashlib.sha256(video.read_bytes()).hexdigest()
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "delivery_id": "TEST-001",
        "files": {"video": {"path": str(video),
                            "sha256": "0" * 64 if fake_hash else digest}},
        "qa": {"ok": qa_ok, "verifier": "qa-01"},
        "contributors": [{"worker": "c-art", "department": "creative"},
                         {"worker": "q-qa", "department": "quality"}],
        "ffprobe": {"format": {"duration": "1.0"}},
    }), encoding="utf-8")
    return manifest, video


def test_register_verifies_real_file_and_qa(tmp_path):
    manifest, _ = _manifest(tmp_path)
    record = artifact_registry.register(tmp_path, manifest)
    assert record["verified"] is True
    assert record["department_ids"] == ["creative", "quality"]
    assert artifact_registry.verify(tmp_path, "TEST-001")["verified"] is True


def test_hash_mismatch_or_missing_file_never_verified(tmp_path):
    manifest, video = _manifest(tmp_path, fake_hash=True)
    assert artifact_registry.register(tmp_path, manifest)["verified"] is False
    manifest2, video2 = _manifest(tmp_path, qa_ok=False)
    assert artifact_registry.register(tmp_path, manifest2)["verified"] is False
    video2.unlink()
    assert artifact_registry.verify(tmp_path, "TEST-001")["verified"] is False
    assert artifact_registry.verify(tmp_path, "TEST-001")["file_exists"] is False


def test_unknown_artifact_raises(tmp_path):
    with pytest.raises(KeyError):
        artifact_registry.verify(tmp_path, "yok")
