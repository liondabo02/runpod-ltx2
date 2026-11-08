"""Offline check of the generated AHOS kite prop and its stored proof.

This tests the GLB structure and SHA-256 proofs, but cannot replace visual
inspection or opening the .blend file in Blender.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

COLORS = ("RED", "YELLOW", "BLUE", "GREEN", "ORANGE", "PURPLE")
FILES = (
    "kite-six-strip-PROPOSED.blend",
    "kite-six-strip-PROPOSED.glb",
    "kite-six-strip-preview.png",
)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()


def read_glb(path: Path) -> dict:
    blob = path.read_bytes()
    if len(blob) < 20:
        raise ValueError("GLB too short")
    magic, version, size = struct.unpack_from("<4sII", blob, 0)
    if magic != b"glTF" or version != 2 or size != len(blob):
        raise ValueError("Invalid GLB header, version or size")
    chunk_size, kind = struct.unpack_from("<I4s", blob, 12)
    if kind != b"JSON" or 20 + chunk_size > len(blob):
        raise ValueError("GLB JSON chunk invalid")
    return json.loads(blob[20:20 + chunk_size].decode("utf-8"))


def validate(directory: Path) -> dict:
    issues: list[str] = []
    report_path = directory / "prop-proof.json"
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"ok": False, "issues": ["missing_or_invalid_proof"]}

    if report.get("asset_id") != "kite-six-strip-tail":
        issues.append("asset_id_mismatch")
    if report.get("status") != "PROPOSED_3D_PROP_QA" or report.get("owner_approved") is not False:
        issues.append("not_a_proposed_unapproved_asset")
    if report.get("strip_count") != 6:
        issues.append("strip_count_mismatch")
    if [str(x).upper() for x in report.get("colors", [])] != list(COLORS):
        issues.append("tail_color_order_mismatch")

    for name in FILES:
        path = directory / name
        proof = (report.get("outputs") or {}).get(name) or {}
        if not path.is_file():
            issues.append("missing:" + name)
            continue
        if path.stat().st_size < 1000:
            issues.append("too_small:" + name)
        if proof.get("size") != path.stat().st_size or proof.get("sha256") != sha256(path):
            issues.append("hash_mismatch:" + name)

    blend = directory / FILES[0]
    if blend.is_file() and b"BLENDER" not in blend.open("rb").read(32):
        issues.append("invalid_blend_header")
    image = directory / FILES[2]
    if image.is_file() and image.open("rb").read(8) != b"\x89PNG\r\n\x1a\n":
        issues.append("invalid_png_header")

    nodes = []
    glb = directory / FILES[1]
    if glb.is_file():
        try:
            content = read_glb(glb)
            nodes = content.get("nodes") or []
            meshes = content.get("meshes") or []
            indexed = {node.get("name"): node for node in nodes}
            expected = ["AHOS_KITE_DIAMOND", "KITE_CROSSBAR", "KITE_SPINE"] + [
                f"KITE_TAIL_{i:02d}_{color}" for i, color in enumerate(COLORS, 1)
            ]
            if len(indexed) != 9 or set(indexed) != set(expected):
                issues.append("nine_mesh_names_mismatch")
            for name in expected:
                node = indexed.get(name) or {}
                index = node.get("mesh")
                if not isinstance(index, int) or not (0 <= index < len(meshes)):
                    issues.append("missing_mesh_data:" + name)
        except (OSError, ValueError, json.JSONDecodeError):
            issues.append("invalid_glb")
    return {"ok": not issues, "issues": issues,
            "asset_id": report.get("asset_id"),
            "status": report.get("status"),
            "mesh_nodes": len(nodes),
            "strip_count": report.get("strip_count"),
            "owner_approved": report.get("owner_approved")}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    result = validate(args.output_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
