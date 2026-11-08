"""Offline unit tests; actual Blender rendering is verified separately on Kahta."""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from validate_kite_prop import read_glb, validate  # noqa: E402


def _glb(doc: dict) -> bytes:
    chunk = json.dumps(doc, separators=(",", ":")).encode("utf-8")
    chunk += b" " * ((4 - len(chunk) % 4) % 4)
    total = 12 + 8 + len(chunk)
    return (struct.pack("<4sII", b"glTF", 2, total)
            + struct.pack("<I4s", len(chunk), b"JSON") + chunk)


def test_missing_proof_is_failing_and_read_only(tmp_path):
    report = validate(tmp_path)
    assert report["ok"] is False
    assert "missing_or_invalid_proof" in report["issues"]
    assert list(tmp_path.iterdir()) == []


def test_glb_parser_checks_declared_length_and_version(tmp_path):
    p = tmp_path / "model.glb"
    p.write_bytes(_glb({"asset": {"version": "2.0"}, "nodes": [], "meshes": []}))
    assert read_glb(p)["asset"]["version"] == "2.0"
    p.write_bytes(p.read_bytes() + b"extra")
    with pytest.raises(ValueError, match="Invalid GLB"):
        read_glb(p)
    data = bytearray(_glb({"nodes": [], "meshes": []}))
    struct.pack_into("<I", data, 4, 3)
    p.write_bytes(data)
    with pytest.raises(ValueError, match="Invalid GLB"):
        read_glb(p)


def test_unapproved_gate_never_accepts_forged_approval(tmp_path):
    (tmp_path / "prop-proof.json").write_text(
        json.dumps({"asset_id": "kite-six-strip-tail",
                    "status": "PROPOSED_3D_PROP_QA",
                    "owner_approved": True,
                    "strip_count": 6,
                    "colors": ["red", "yellow", "blue", "green", "orange", "purple"]}),
        encoding="utf-8"
    )
    result = validate(tmp_path)
    assert result["ok"] is False
    assert "not_a_proposed_unapproved_asset" in result["issues"]
    assert any(x.startswith("missing:") for x in result["issues"])


def test_tracked_asset_index_does_not_claim_owner_approval():
    data = json.loads(
        (ROOT / "studio" / "production" / "asset-proofs"
         / "kite-six-strip-20261108.json").read_text(encoding="utf-8")
    )
    assert data["asset_id"] == "kite-six-strip-tail"
    assert data["status"] == "PROPOSED_3D_PROP_QA"
    assert data["owner_approved"] is False
    assert data["mesh_nodes"] == 9
    assert data["tail_strip_meshes"] == 6
    assert len(data["outputs"]) == 3
    assert all(len(item["sha256"]) == 64 and item["size"] > 1000
               for item in data["outputs"])
