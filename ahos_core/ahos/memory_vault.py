"""Non-destructive memory vault for AHOS.

Live SQLite is copied using the SQLite backup API; worker memories and
learning files are checksummed inside an offline archive. This module never
restores, deletes existing backups, changes permissions, or sends data online.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import time
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile

SCHEMA = "ahos.memory-vault.v1"
DIRECTORIES = ("minds", "learning", "cognition", "brains", "departments",
               "goals", "knowledge", "ceo", "ideas")
ROOT_FILES = ("departments.json", "worker-metrics.jsonl",
              "initiative.jsonl", "daemon-state.json")
ALLOWED_EXTENSIONS = {".json", ".jsonl", ".md", ".txt", ".yaml", ".yml"}
EXCLUDED_NAME_PARTS = (".env", "secret", "token", "password", "credential",
                       "private_key", "api-key", "apikey", ".pem", ".p12")
MAX_FILE_SIZE = 32 * 1024 * 1024
MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
DEFAULT_INTERVAL_SECONDS = 6 * 3600


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _atomic_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temp.open("x", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _trusted_source_files(runtime: Path) -> list[tuple[str, Path]]:
    selected: list[tuple[str, Path]] = []
    paths = [runtime / name for name in ROOT_FILES]
    for folder in DIRECTORIES:
        base = runtime / folder
        if base.is_symlink():
            continue
        if base.is_dir():
            paths.extend(base.rglob("*"))
    for path in paths:
        if path.is_symlink() or not path.is_file():
            continue
        if not path.resolve().is_relative_to(runtime.resolve()):
            # A nested symlink must never pull in material outside runtime.
            continue
        relative = path.relative_to(runtime)
        names = [part.lower() for part in relative.parts]
        if (path.suffix.lower() not in ALLOWED_EXTENSIONS
                or any(any(sensitive in part for sensitive in EXCLUDED_NAME_PARTS)
                       for part in names)):
            continue
        if path.stat().st_size > MAX_FILE_SIZE:
            raise ValueError("memory source exceeds safe size: " + relative.as_posix())
        selected.append((relative.as_posix(), path))
    return sorted(selected, key=lambda pair: pair[0])


def _sqlite_check(db_path: Path) -> None:
    with closing(sqlite3.connect("file:" + db_path.resolve().as_posix()
                                 + "?mode=ro", uri=True)) as conn:
        result = conn.execute("PRAGMA quick_check").fetchone()
    if not result or result[0] != "ok":
        raise ValueError("SQLite backup integrity check failed")


def verify(snapshot_dir: str | Path) -> dict:
    """Verify the sealed snapshot, all files and SQLite integrity. Read only."""
    folder = Path(snapshot_dir)
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema") != SCHEMA:
        raise ValueError("unsupported memory-vault manifest schema")
    listed = manifest.get("files")
    if not isinstance(listed, dict):
        raise ValueError("invalid memory-vault file manifest")
    archive_path = folder / "memories.zip"
    database_path = folder / "company-service.db"
    for filename, path in (("memories.zip", archive_path),
                           ("company-service.db", database_path)):
        expected = manifest.get("artifacts", {}).get(filename) or {}
        if _digest(path.read_bytes()) != expected.get("sha256"):
            raise ValueError("corrupted snapshot artifact: " + filename)

    with ZipFile(archive_path) as archive:
        if archive.testzip():
            raise ValueError("memory archive failed CRC check")
        if set(archive.namelist()) != set(listed):
            raise ValueError("memory archive manifest mismatch")
        for name, information in listed.items():
            if (name.startswith("/") or "\\" in name
                    or ".." in Path(name).parts):
                raise ValueError("unsafe archived filename")
            content = archive.read(name)
            if (len(content) != information.get("bytes")
                    or _digest(content) != information.get("sha256")):
                raise ValueError("memory file integrity failure: " + name)
    _sqlite_check(database_path)
    return {
        "verified": True,
        "files": len(listed),
        "sqlite_bytes": database_path.stat().st_size,
        "schema": SCHEMA,
        "snapshot": str(folder),
    }


def snapshot(runtime_dir: str | Path, backup_root: str | Path) -> dict:
    """Consistent online DB backup + independent immutable-by-policy archive."""
    runtime = Path(runtime_dir).resolve()
    root = Path(backup_root).resolve()
    database = runtime / "company-service.db"
    if not database.is_file():
        raise FileNotFoundError("cannot protect AHOS runtime without its SQLite DB")
    if root == runtime or runtime in root.parents or root in runtime.parents:
        raise ValueError("backup root must be separate from live runtime")
    root.mkdir(parents=True, exist_ok=True)
    folder = root / ("vault-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                     + "-" + uuid.uuid4().hex[:8])
    folder.mkdir(exist_ok=False)
    db_copy = folder / "company-service.db"
    try:
        # The online SQLite backup API copies a consistent transaction snapshot.
        with closing(sqlite3.connect("file:" + database.as_posix() + "?mode=ro",
                                     uri=True, timeout=30)) as source:
            with closing(sqlite3.connect(db_copy, timeout=30)) as destination:
                source.backup(destination, pages=1000, sleep=0.05)
                destination.commit()
        _sqlite_check(db_copy)

        entries: dict[str, dict] = {}
        total = 0
        with ZipFile(folder / "memories.zip", "w", compression=ZIP_DEFLATED,
                     compresslevel=6) as archive:
            for name, file in _trusted_source_files(runtime):
                # Snapshot the exact bytes we checksum, even if the live file
                # changes before the archive finishes being written.
                data = file.read_bytes()
                total += len(data)
                if total > MAX_ARCHIVE_BYTES:
                    raise ValueError("memory archive exceeds safety size ceiling")
                archive.writestr(name, data)
                entries[name] = {"bytes": len(data), "sha256": _digest(data)}
        artifacts: dict[str, dict] = {}
        for filename in ("memories.zip", "company-service.db"):
            path = folder / filename
            artifacts[filename] = {
                "bytes": path.stat().st_size,
                "sha256": _digest(path.read_bytes()),
            }
        _atomic_json(folder / "manifest.json", {
            "schema": SCHEMA,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "source_runtime": str(runtime),
            "files": entries,
            "artifacts": artifacts,
            "restore_policy": "preview_only_manual_owner_approval_required",
            "secret_paths_excluded": True,
            "content_secret_scan_performed": False,
            "note": "SQLite transaction-consistent; non-DB files sampled individually",
        })
        result = verify(folder)
        result["created_at"] = time.time()
        return result
    except Exception:
        # Preserve incomplete artifacts for inspection. Never touch existing
        # backups and never claim success if any integrity check failed.
        raise


def default_backup_root(runtime_dir: str | Path) -> Path:
    """For repo/ahos_core/runtime, save beside repo, never in Git/runtime."""
    runtime = Path(runtime_dir).resolve()
    if runtime.name != "runtime" or runtime.parent.name != "ahos_core":
        raise ValueError("default vault location requires ahos_core/runtime layout")
    project_root = runtime.parents[1]
    target_parent = project_root.parent
    # GitHub Actions checkouts frequently repeat the repository directory:
    # .../_work/runpod-ltx2/runpod-ltx2. Keep backups in the established
    # .../_work/AHOS_BACKUPS location, safely outside both checkouts.
    if target_parent.name.casefold() == project_root.name.casefold():
        target_parent = target_parent.parent
    return target_parent / "AHOS_BACKUPS"


def snapshot_if_due(runtime_dir: str | Path, backup_root: str | Path | None = None,
                    *, every_seconds: int = DEFAULT_INTERVAL_SECONDS,
                    now: float | None = None) -> dict:
    """Bounded daemon hook; concurrent calls never write to the same snapshot."""
    runtime = Path(runtime_dir)
    root = (Path(backup_root) if backup_root is not None
            else default_backup_root(runtime))
    if every_seconds <= 0:
        raise ValueError("snapshot interval must be positive")
    root.mkdir(parents=True, exist_ok=True)
    marker = root / ".memory-vault-last-success.json"
    epoch = time.time() if now is None else float(now)
    try:
        previous = json.loads(marker.read_text(encoding="utf-8"))
        last = float(previous["created_at"])
        saved = Path(previous["snapshot"])
        if (last <= epoch and epoch - last < every_seconds
                and saved.is_dir()
                and saved.resolve().is_relative_to(root.resolve())):
            try:
                verify(saved)
            except (OSError, ValueError, BadZipFile, KeyError, TypeError):
                # The prior backup must never be called healthy if tampered.
                # Preserve it for investigation and take a fresh snapshot.
                pass
            else:
                return {"status": "fresh", "last_snapshot": str(saved)}
    except (OSError, KeyError, ValueError, TypeError):
        pass

    lock_path = root / ".memory-vault.lock"
    try:
        handle = os.open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return {"status": "locked", "reason": "another_snapshot_in_progress"}
    try:
        os.write(handle, str(os.getpid()).encode("ascii"))
        os.close(handle)
        result = snapshot(runtime, root)
        _atomic_json(marker, {
            "created_at": epoch, "snapshot": result["snapshot"],
            "verified": result["verified"], "files": result["files"],
        })
        return {"status": "saved", **result}
    finally:
        lock_path.unlink(missing_ok=True)


def audit_worker_minds(runtime_dir: str | Path) -> dict:
    """Read-only check; report missing/corrupt memories without deleting them."""
    runtime = Path(runtime_dir)
    try:
        book = json.loads((runtime / "departments.json").read_text(encoding="utf-8"))
        roster = book["departments"] if isinstance(book, dict) else book
    except (OSError, ValueError, TypeError, KeyError):
        return {"ok": False, "reason": "roster_unavailable"}
    missing: list[str] = []
    invalid: list[str] = []
    observed = 0
    for dep in roster:
        for entry in dep.get("workers", []):
            worker_id = str(entry.get("worker_id", ""))
            if not worker_id:
                continue
            observed += 1
            if not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", worker_id):
                invalid.append(worker_id[:128])
                continue
            path = runtime / "minds" / (worker_id + ".json")
            if not path.exists():
                missing.append(worker_id)
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(data, dict) or data.get("worker_id") != worker_id:
                    invalid.append(worker_id)
            except (OSError, ValueError, TypeError):
                invalid.append(worker_id)
    return {
        "ok": not missing and not invalid, "rostered": observed,
        "missing": missing, "invalid": invalid,
    }
