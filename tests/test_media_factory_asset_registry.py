"""Media factory asset reuse: hashes, invalidation, missing files."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from media_factory.asset_registry import (find_reusable, register, sha256_file,
                                          verify)  # noqa: E402


def make_asset(tmp_path: Path) -> tuple[Path, str]:
    source = tmp_path / "source.png"
    source.write_bytes(b"canonical-roster-bytes" * 20)
    asset = tmp_path / "model.glb"
    asset.write_bytes(b"glTF" + b"A" * 300)
    return asset, sha256_file(source)


def test_register_and_reuse_exact_hashes(tmp_path):
    asset, source_sha = make_asset(tmp_path)
    registry = tmp_path / "registry.json"
    first = register(asset, "aden", "character_model", "roster/01_aden.png", source_sha,
                     "blender", "original procedural geometry", registry_path=registry)
    assert first["reused_existing"] is False
    assert first["record"]["identity_approved"] is False
    found = find_reusable("aden", "character_model", source_sha, registry)
    assert found and found["geometry_sha256"] == sha256_file(asset)
    again = register(asset, "aden", "character_model", "roster/01_aden.png", source_sha,
                     "blender", "original procedural geometry", registry_path=registry)
    assert again["reused_existing"] is True


def test_source_change_invalidates_cache(tmp_path):
    asset, source_sha = make_asset(tmp_path)
    registry = tmp_path / "registry.json"
    register(asset, "aden", "character_model", "roster/01_aden.png", source_sha,
             "blender", "original procedural geometry", registry_path=registry)
    assert find_reusable("aden", "character_model", "0" * 64, registry) is None


def test_tampered_or_missing_asset_is_reported(tmp_path):
    asset, source_sha = make_asset(tmp_path)
    registry = tmp_path / "registry.json"
    register(asset, "aden", "character_model", "roster/01_aden.png", source_sha,
             "blender", "original procedural geometry", registry_path=registry)
    asset.write_bytes(b"glTF" + b"B" * 300)
    assert any("hash mismatch" in issue for issue in verify(registry))
    asset.unlink()
    assert any("missing file" in issue for issue in verify(registry))
