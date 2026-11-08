"""Create verified, non-destructive snapshots of AHOS runtime state.

SQLite databases are copied through SQLite's online backup API rather than
reading the potentially stale main DB file while a WAL writer is active.
The backup contains no known configuration files, access tokens or secrets.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import tempfile
import time
import zipfile
from pathlib import Path

KEEP = 7
INCLUDE = (
    "company-service.db",
    "owner-approvals.db",
    "daemon-state.json",
    "autonomy-state.json",
    "auto-scheduler-state.json",
    "auto-plan.json",
    "departments.json",
    "projects.json",
    "self-improvement.jsonl",
    "self-improvement-done.jsonl",
    "daemon-missions.jsonl",
    "model-spend.jsonl",
    "ceo-thread.jsonl",
    "worker-metrics.jsonl",
    "taskboard.json",
    "audit.jsonl",
    "live-events.jsonl",
    "chronicle.jsonl",
    "owner-commands.jsonl",
    "ideas",
    "knowledge",
    "brains",
    "companies",
    "ceo",
    "tasks",
    "subagents",
)
SQLITE_FILES = frozenset({"company-service.db", "owner-approvals.db"})
SENSITIVE_PARTS = ("token", "secret", "credential", "password", ".env", "private.key")


def _safe_file(root: Path, source: Path) -> bool:
    """Allow only ordinary files within runtime; never follow external symlinks."""
    if source.is_symlink() or not source.is_file():
        return False
    if not source.resolve().is_relative_to(root.resolve()):
        return False
    relative = source.relative_to(root)
    return not any(
        marker in part.casefold()
        for part in relative.parts
        for marker in SENSITIVE_PARTS
    )


def _sqlite_snapshot(path: Path) -> bytes:
    """Capture WAL commits in an on-disk snapshot with an ordinary SQLite header."""
    with tempfile.TemporaryDirectory(prefix=".ahos-db-snapshot-", dir=path.parent) as temp:
        snapshot = Path(temp) / "snapshot.db"
        source = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True, timeout=30)
        try:
            destination = sqlite3.connect(snapshot)
            try:
                source.backup(destination, pages=128, sleep=0.02)
                destination.execute("PRAGMA journal_mode=DELETE")
            finally:
                destination.close()
        finally:
            source.close()
        return snapshot.read_bytes()


def verify_archive(path: str | Path) -> dict:
    """Verify the archive CRC and every manifest SHA-256 before claiming success."""
    with zipfile.ZipFile(path) as bundle:
        bad_member = bundle.testzip()
        if bad_member:
            raise ValueError(f"backup CRC mismatch: {bad_member}")
        manifest = json.loads(bundle.read("runtime/backup-manifest.json"))
        files = manifest.get("files")
        if not isinstance(files, dict) or not files:
            raise ValueError("backup manifest is empty")
        for name, info in files.items():
            if name not in bundle.namelist():
                raise ValueError(f"backup file missing: {name}")
            content = bundle.read(name)
            if hashlib.sha256(content).hexdigest() != info.get("sha256"):
                raise ValueError(f"backup SHA-256 mismatch: {name}")
            if len(content) != info.get("bytes"):
                raise ValueError(f"backup size mismatch: {name}")
        return {"verified_files": len(files), "schema": manifest.get("schema")}


def backup(runtime_dir: str | Path) -> Path | None:
    runtime = Path(runtime_dir)
    if not runtime.is_dir():
        return None
    target_dir = runtime / "backups"
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    archive = target_dir / f"runtime-{stamp}.zip"
    index = 1
    while archive.exists():
        index += 1
        archive = target_dir / f"runtime-{stamp}-{index}.zip"

    manifest: dict[str, object] = {
        "schema": "ahos.runtime-backup.v2",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "scope": "per-file snapshot; cross-file atomicity is not guaranteed",
        "files": {},
    }
    written = 0
    with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED) as bundle:
        for name in INCLUDE:
            source = runtime / name
            if not source.exists():
                continue
            files = (source.rglob("*") if source.is_dir() and not source.is_symlink()
                     else (source,))
            for path in files:
                if not _safe_file(runtime, path):
                    continue
                relative = path.relative_to(runtime).as_posix()
                arc_name = f"runtime/{relative}"
                payload = (_sqlite_snapshot(path) if relative in SQLITE_FILES
                           else path.read_bytes())
                bundle.writestr(arc_name, payload)
                manifest["files"][arc_name] = {
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "bytes": len(payload),
                }
                written += 1
        if not written:
            raise ValueError("runtime has no backup-eligible files")
        bundle.writestr(
            "runtime/backup-manifest.json",
            json.dumps(manifest, ensure_ascii=False, sort_keys=True),
        )

    verify_archive(archive)
    archives = sorted(target_dir.glob("runtime-*.zip"))
    for old in archives[:-KEEP]:
        destination = old.with_suffix(".zip.old")
        serial = 1
        while destination.exists():
            serial += 1
            destination = old.with_suffix(f".zip.old.{serial}")
        old.rename(destination)
    print(f"yedek doğrulandı: {archive.name} · {written} dosya")
    return archive


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # pragma: no cover
        pass
    args = list(sys.argv[1:] if argv is None else argv)
    runtime = Path("runtime")
    if "--runtime-dir" in args:
        position = args.index("--runtime-dir")
        runtime = Path(args[position + 1])
    return 0 if backup(runtime) else 2


if __name__ == "__main__":
    raise SystemExit(main())
