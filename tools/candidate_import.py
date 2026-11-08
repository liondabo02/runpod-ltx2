"""Aden aday görsel içe aktarma — orijinali değiştirmez, onay vermez."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

from PIL import Image

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
ALLOWED = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG"}
STATUS = "CANDIDATE_PENDING_REVIEW"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def import_candidate(character: str, image: Path, *, root: Path = ROOT,
                     source: str = "external", note: str = "") -> dict:
    if (root / "studio/characters" / character / "portrait-design.json").is_file() and character.isidentifier():
        from p7_portraits import import_portrait
        return import_portrait(root, character, image, source=source, model="UNKNOWN",
                               prompt=note or "UNKNOWN", license_status="UNVERIFIED")
    if character != "aden":
        raise SystemExit("P6 yalnız aden adayı kabul eder")
    suffix = image.suffix.lower()
    if suffix not in ALLOWED:
        raise SystemExit(f"desteklenmeyen biçim: {suffix}")
    if not image.is_file():
        raise SystemExit(f"dosya yok: {image}")
    try:
        with Image.open(image) as checked:
            width, height = checked.size
            checked.verify()
    except Exception as exc:  # noqa: BLE001 - bozuk dosya aday sayılmaz
        raise SystemExit(f"görsel açılamadı: {exc}") from exc
    if width < 512 or height < 512:
        raise SystemExit(f"görsel çok küçük: {width}x{height}")

    digest = sha256(image)
    candidates = root / "studio" / "candidates" / character
    candidates.mkdir(parents=True, exist_ok=True)
    target = candidates / f"{digest[:12]}{suffix}"
    if not target.exists():
        shutil.copyfile(image, target)
    if sha256(target) != digest:
        raise SystemExit("kopya hash uyuşmuyor")

    dna = root / "studio" / "characters" / character / "visual-dna.json"
    record = {
        "schema": "ahos.studio.candidate.v1",
        "character_id": character,
        "status": STATUS,
        "path": str(target.relative_to(root)).replace("\\", "/"),
        "sha256": digest,
        "bytes": target.stat().st_size,
        "width": width,
        "height": height,
        "source": source,
        "source_file": str(image),
        "note": note,
        "visual_dna": {"path": str(dna.relative_to(root)).replace("\\", "/"),
                        "sha256": sha256(dna)},
        "owner_approval": "NONE",
        "identity_lock_modified": False,
        "final_use_allowed": False,
        "imported_at": "2026-11-08",
    }
    meta = candidates / f"{digest[:12]}.json"
    meta.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    registry_path = candidates / "registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8")) if registry_path.is_file() else {
        "schema": "ahos.studio.candidate-registry.v1", "character_id": character, "candidates": []}
    registry["candidates"] = [row for row in registry["candidates"] if row["sha256"] != digest]
    registry["candidates"].append({"sha256": digest, "path": record["path"], "status": STATUS,
                                    "source": source, "owner_approval": "NONE"})
    registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--character", default="aden")
    parser.add_argument("--image", required=True)
    parser.add_argument("--source", default="external")
    parser.add_argument("--note", default="")
    args = parser.parse_args(argv)
    record = import_candidate(args.character, Path(args.image), source=args.source, note=args.note)
    print(json.dumps({key: record[key] for key in ("status", "path", "sha256", "width", "height")},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
