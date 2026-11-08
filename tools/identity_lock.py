"""16 karakter için sürümlü, doğrulanabilir kimlik kilidi.

Kullanım:
    python tools/identity_lock.py --build --source-commit e77f7ef
    python tools/identity_lock.py --verify
    python tools/identity_lock.py --change aden --reason "..."
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
CHARACTERS = ROOT / "studio" / "characters"
LOCK = ROOT / "studio" / "identity" / "identity-lock.json"
FILES = ("character.json", "visual-dna.json", "color-palette.json",
         "motion-profile.json", "voice-profile.json", "model-spec.json")
DATE = "2026-11-08"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_json(path: Path) -> bytes:
    return json.dumps(json.loads(path.read_text(encoding="utf-8")),
                      ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def character_record(cid: str) -> dict:
    base = CHARACTERS / cid
    files = {}
    parts = []
    for name in FILES:
        path = base / name
        if not path.is_file():
            continue
        files[name] = sha256(path)
        parts.append(name.encode() + b"\0" + canonical_json(path))
    identity = hashlib.sha256(b"\n".join(parts)).hexdigest()
    return {"character_id": cid, "files": files, "identity_sha256": identity}


def build(source_commit: str) -> dict:
    existing = json.loads(LOCK.read_text(encoding="utf-8")) if LOCK.is_file() else {}
    old = {row["character_id"]: row for row in existing.get("characters", [])}
    rows = []
    for cid in sorted(path.name for path in CHARACTERS.iterdir() if path.is_dir()):
        record = character_record(cid)
        previous = old.get(cid)
        history = list(previous.get("history", [])) if previous else []
        version = previous.get("canon_version", "1.0.0") if previous else "1.0.0"
        if previous and previous.get("identity_sha256") != record["identity_sha256"]:
            history.append({"date": DATE, "change": "içerik değişti; yeniden kilitlendi",
                            "from": previous.get("identity_sha256"), "to": record["identity_sha256"]})
        elif not history:
            history.append({"date": DATE, "change": "ilk kimlik kilidi",
                            "from": None, "to": record["identity_sha256"]})
        rows.append({"character_id": cid, "canon_version": version,
                     "lock_status": "LOCKED_FOR_EDIT", "approval_status": "NONE",
                     "approved_by": None, "approved_at": None,
                     "locked_at": previous.get("locked_at", DATE) if previous else DATE,
                     "source_commit": source_commit,
                     "identity_sha256": record["identity_sha256"], "files": record["files"],
                     "history": history})
    payload = {"schema": "ahos.studio.identity-lock.v1", "generated_at": DATE,
               "character_count": len(rows),
               "rule": "Kimlik kilidi onay değildir; APPROVED yalnız sahip kaydıyla verilir.",
               "characters": rows}
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    LOCK.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def verify(lock_path: Path | None = None, characters: Path | None = None) -> list[str]:
    lock_path = lock_path or LOCK
    characters = characters or CHARACTERS
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    problems = []
    if lock.get("character_count") != 16:
        problems.append("16 karakter yok")
    for row in lock.get("characters", []):
        base = characters / row["character_id"]
        current = {"files": {}, "identity_sha256": ""}
        parts = []
        for name in FILES:
            path = base / name
            if not path.is_file():
                continue
            current["files"][name] = sha256(path)
            parts.append(name.encode() + b"\0" + canonical_json(path))
        current["identity_sha256"] = hashlib.sha256(b"\n".join(parts)).hexdigest()
        if current["identity_sha256"] != row["identity_sha256"]:
            problems.append(f"{row['character_id']}: kimlik hash uyuşmuyor")
        for name, digest in row.get("files", {}).items():
            if current["files"].get(name) != digest:
                problems.append(f"{row['character_id']}: {name} değişmiş")
        if row.get("approval_status") == "APPROVED" and not row.get("approved_by"):
            problems.append(f"{row['character_id']}: onaysız APPROVED")
    return problems


def change(cid: str, reason: str) -> dict:
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    row = next((item for item in lock["characters"] if item["character_id"] == cid), None)
    if row is None:
        raise SystemExit(f"bilinmeyen karakter: {cid}")
    if not reason.strip():
        raise SystemExit("değişiklik gerekçesi zorunlu")
    current = character_record(cid)
    major, minor, patch = (int(part) for part in row["canon_version"].split("."))
    version = f"{major}.{minor + 1}.{patch}"
    row["canon_version"] = version
    row["history"].append({"date": DATE, "change": reason, "from": row["identity_sha256"],
                           "to": current["identity_sha256"]})
    row["identity_sha256"] = current["identity_sha256"]
    row["files"] = current["files"]
    row["approval_status"] = "NONE"
    row["approved_by"] = None
    row["approved_at"] = None
    LOCK.write_text(json.dumps(lock, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return row


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--change")
    parser.add_argument("--reason", default="")
    parser.add_argument("--source-commit", default="e77f7ef")
    args = parser.parse_args(argv)
    if args.build:
        payload = build(args.source_commit)
        print(json.dumps({"built": payload["character_count"], "path": str(LOCK)}, ensure_ascii=False))
        return 0
    if args.change:
        row = change(args.change, args.reason)
        print(json.dumps({"character": row["character_id"], "version": row["canon_version"]},
                         ensure_ascii=False))
        return 0
    problems = verify()
    print(json.dumps({"ok": not problems, "problems": problems}, ensure_ascii=False, indent=2))
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
