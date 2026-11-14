"""SHA-256 based reusable asset registry for the AHOS media factory.

Only real files are registered. Reuse requires an exact canonical source hash
AND an intact asset hash; a filename match is never enough. No approval is
implied: identity/license fields are recorded separately.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY = Path(os.environ.get(
    "AHOS_ASSET_REGISTRY", ROOT / "studio/assets/media-factory/registry.json"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load(path: Path) -> dict:
    if not path.is_file():
        return {"schema": "ahos.media-factory.asset-registry.v1", "assets": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != "ahos.media-factory.asset-registry.v1":
        raise ValueError("asset registry schema mismatch")
    if not isinstance(data.get("assets"), list):
        raise ValueError("asset registry assets must be a list")
    return data


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def register(asset_path: Path, character_id: str, asset_type: str,
             source_reference: str, source_sha256: str, engine: str,
             license_provenance: str, identity_status: str = "PENDING_IDENTITY_REVIEW",
             registry_path: Path = DEFAULT_REGISTRY) -> dict:
    asset_path = Path(asset_path).resolve()
    if not asset_path.is_file() or asset_path.stat().st_size < 100:
        raise ValueError("asset file missing or too small")
    if len(source_sha256) != 64:
        raise ValueError("canonical source SHA-256 required")
    asset_sha = sha256_file(asset_path)
    data = _load(registry_path)
    for record in data["assets"]:
        if (record["character_id"] == character_id and record["asset_type"] == asset_type
                and record["canonical_reference_sha256"] == source_sha256
                and record["geometry_sha256"] == asset_sha):
            return {"record": record, "reused_existing": True}
    version = 1 + max(
        (r["approved_version"] for r in data["assets"]
         if r["character_id"] == character_id and r["asset_type"] == asset_type),
        default=0)
    record = {
        "asset_id": f"{character_id}:{asset_type}:v{version}",
        "character_id": character_id,
        "asset_type": asset_type,
        "canonical_reference_sha256": source_sha256,
        "geometry_sha256": asset_sha,
        "asset_path": str(asset_path.relative_to(ROOT)) if ROOT in asset_path.parents else str(asset_path),
        "bytes": asset_path.stat().st_size,
        "approved_version": version,
        "license_provenance": license_provenance,
        "identity_review_status": identity_status,
        "identity_approved": False,
        "creation_engine": engine,
        "reuse_policy": "reuse_only_if_canonical_and_asset_hash_match",
        "dependencies": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_reference": source_reference,
    }
    data["assets"].append(record)
    _write(registry_path, data)
    return {"record": record, "reused_existing": False}


def find_reusable(character_id: str, asset_type: str, source_sha256: str,
                  registry_path: Path = DEFAULT_REGISTRY) -> dict | None:
    data = _load(registry_path)
    matches = []
    for record in data["assets"]:
        if (record["character_id"] == character_id and record["asset_type"] == asset_type
                and record["canonical_reference_sha256"] == source_sha256):
            path = ROOT / record["asset_path"] if not Path(record["asset_path"]).is_absolute() \
                else Path(record["asset_path"])
            if path.is_file() and sha256_file(path) == record["geometry_sha256"]:
                matches.append(record)
    return max(matches, key=lambda r: r["approved_version"]) if matches else None


def verify(registry_path: Path = DEFAULT_REGISTRY) -> list[str]:
    issues = []
    for record in _load(registry_path)["assets"]:
        path = ROOT / record["asset_path"] if not Path(record["asset_path"]).is_absolute() \
            else Path(record["asset_path"])
        if not path.is_file():
            issues.append(f"{record['asset_id']}: missing file")
        elif sha256_file(path) != record["geometry_sha256"]:
            issues.append(f"{record['asset_id']}: asset hash mismatch")
        if record.get("identity_approved") is not False:
            issues.append(f"{record['asset_id']}: identity approval must be explicit")
    return issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    sub = parser.add_subparsers(dest="command", required=True)
    reg = sub.add_parser("register")
    reg.add_argument("--asset", type=Path, required=True)
    reg.add_argument("--character", required=True)
    reg.add_argument("--type", required=True)
    reg.add_argument("--source", required=True)
    reg.add_argument("--source-sha", required=True)
    reg.add_argument("--engine", required=True)
    reg.add_argument("--license", required=True)
    find = sub.add_parser("find")
    find.add_argument("--character", required=True)
    find.add_argument("--type", required=True)
    find.add_argument("--source-sha", required=True)
    sub.add_parser("verify")
    args = parser.parse_args(argv)
    if args.command == "register":
        print(json.dumps(register(args.asset, args.character, args.type, args.source,
                                  args.source_sha, args.engine, args.license,
                                  registry_path=args.registry), ensure_ascii=False, indent=2))
        return 0
    if args.command == "find":
        found = find_reusable(args.character, args.type, args.source_sha, args.registry)
        print(json.dumps(found, ensure_ascii=False, indent=2))
        return 0 if found else 2
    issues = verify(args.registry)
    print(json.dumps({"ok": not issues, "issues": issues}, ensure_ascii=False, indent=2))
    return 0 if not issues else 2


if __name__ == "__main__":
    raise SystemExit(main())
