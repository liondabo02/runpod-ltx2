"""Import an owner-accepted AHOS Studio-16 roster ZIP without altering identity locks."""
import argparse
import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path

POSTER_NAME = "AHOS_Studio16_Approved_Poster.png"
DEST_REL = Path("studio") / "reference" / "owner_accepted_roster_v1"
EXPECTED_IDS = (
    "aden", "kaan", "esra", "ahmet", "esma", "harun", "veysel",
    "oznur", "salih", "medine", "davut", "fatos", "emos",
    "berzan", "aras", "ramin",
)

def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def import_pack(archive_path: Path, repo: Path) -> str:
    if not archive_path.is_file():
        raise ValueError(f"ZIP missing: {archive_path}")
    destination = repo / DEST_REL
    with zipfile.ZipFile(archive_path) as archive:
        entries = archive.namelist()
        if len(entries) != len(set(entries)):
            raise ValueError("Duplicate ZIP entry")
        if any(name.startswith("/") or "\\" in name or ".." in Path(name).parts for name in entries):
            raise ValueError("Unsafe ZIP entry")
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        if manifest.get("status") != "ROSTER_POSTER_OWNER_ACCEPTED":
            raise ValueError("Unexpected approval status")
        characters = manifest.get("characters", [])
        if tuple(c.get("id") for c in characters) != EXPECTED_IDS:
            raise ValueError("Character IDs/order mismatch")
        expected = {POSTER_NAME: manifest["source_sha256"]}
        for character in characters:
            filename = character["file"]
            if filename != "characters/" + f"{EXPECTED_IDS.index(character['id'])+1:02d}_{character['id']}.png":
                raise ValueError("Unexpected filename")
            expected[filename] = character["sha256"]
        expected["manifest.json"] = None
        expected["README_TR.md"] = None
        if set(entries) != set(expected):
            raise ValueError("Unexpected/missing archive files")
        if sum(archive.getinfo(name).file_size for name in entries) > 100_000_000:
            raise ValueError("Archive too large")
        data = {name: archive.read(name) for name in entries}
        for filename, expected_hash in expected.items():
            if expected_hash is not None and digest(data[filename]) != expected_hash:
                raise ValueError(f"Hash mismatch: {filename}")
    if destination.exists():
        for filename, raw in data.items():
            target = destination / filename
            if target.exists() and target.read_bytes() != raw:
                raise FileExistsError(f"Refusing to overwrite changed reference: {target}")
    for filename, raw in data.items():
        target = destination / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_bytes(raw)
    return str(destination)

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        print("IMPORTED:", import_pack(args.zip, args.repo))
    except (ValueError, KeyError, OSError, zipfile.BadZipFile) as exc:
        print("FAILED:", exc, file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
