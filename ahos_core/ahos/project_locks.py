"""Cross-process, atomic project lock.

The previous implementation kept ownership in a process-local dict, so two
Python processes (or two panels with different runtime dirs) could both believe
they owned the same project. Ownership is now an OS byte lock on a canonical
lock file; the JSON snapshot is only a human-readable hint and never the
authority.

Canonical location: ``AHOS_LOCK_DIR`` or ``%LOCALAPPDATA%\\ahos-locks`` — never
the runtime dir, so different panels contend on the same file.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

try:  # Windows
    import msvcrt
except ImportError:  # pragma: no cover - posix
    msvcrt = None  # type: ignore[assignment]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def lock_dir() -> Path:
    custom = os.environ.get("AHOS_LOCK_DIR", "").strip()
    if custom:
        return Path(custom)
    base = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
    return Path(base) / "ahos-locks"


def canonical_key(path: str | Path) -> str:
    resolved = str(Path(path).resolve()).lower()
    return hashlib.sha256(resolved.encode("utf-8")).hexdigest()[:32]


def lock_file(path: str | Path) -> Path:
    directory = lock_dir()
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{canonical_key(path)}.lock"


def _try_lock(handle) -> bool:
    if msvcrt is not None:
        try:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            return True
        except OSError:
            return False
    import fcntl as _fcntl

    try:
        _fcntl.flock(handle.fileno(), _fcntl.LOCK_EX | _fcntl.LOCK_NB)
        return True
    except OSError:
        return False


def _unlock(handle) -> None:
    try:
        if msvcrt is not None:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl as _fcntl

            _fcntl.flock(handle.fileno(), _fcntl.LOCK_UN)
    except OSError:  # pragma: no cover - already closed
        pass


def acquire(
    path: str | Path,
    *,
    mission_id: str,
    token_id: str | None = None,
    wait_seconds: float = 0.0,
) -> bool:
    """Atomically take the project lock. False means somebody else owns it."""

    handle = lock_file(path).open("a+b")
    deadline = time.monotonic() + max(0.0, wait_seconds)
    while True:
        if _try_lock(handle):
            payload = json.dumps(
                {
                    "mission_id": mission_id,
                    "token_id": token_id,
                    "pid": os.getpid(),
                    "acquired_at": _now(),
                    "project": str(Path(path).resolve()),
                },
                ensure_ascii=False,
            ).encode("utf-8")
            handle.seek(0)
            handle.truncate()
            handle.write(payload)
            handle.flush()
            # Keep the handle open: closing it would release the OS lock.
            _HANDLES[str(Path(path).resolve())] = handle
            _OWNERS[str(Path(path).resolve())] = mission_id
            return True
        if time.monotonic() >= deadline:
            handle.close()
            return False
        time.sleep(0.05)


def release(path: str | Path, *, mission_id: str | None = None) -> bool:
    key = str(Path(path).resolve())
    handle = _HANDLES.pop(key, None)
    if handle is None:
        return False
    owner = _OWNERS.get(key)
    if owner is None:
        owner = str(_read_metadata(path).get("mission_id") or "")
    if mission_id is not None and owner != mission_id:
        # Yanlış sahip kilidi bırakamaz: handle geri konur.
        _HANDLES[key] = handle
        return False
    _unlock(handle)
    handle.close()
    _OWNERS.pop(key, None)
    return True


def holder(path: str | Path) -> dict[str, object] | None:
    """Owner of the *currently held* lock; None only when the project is free.

    Metadata can be unreadable while another process holds the OS lock, so a
    locked-but-unreadable project reports ``unknown-owner`` (fail-closed) rather
    than pretending it is free.
    """

    if not probe(path):
        return None
    metadata = _read_metadata(path)
    if not metadata:
        owner = _OWNERS.get(str(Path(path).resolve()))
        if owner:
            # Bu süreç tutuyor: metadata diskten okunamasa da sahibi biliyoruz.
            return {
                "mission_id": owner,
                "pid": os.getpid(),
                "acquired_at": None,
                "reason": "bu süreç tutuyor (metadata okunamadı)",
            }
        return {
            "mission_id": "unknown-owner",
            "pid": None,
            "acquired_at": None,
            "reason": "kilit tutuluyor, sahiplik metadatası okunamadı (fail-closed)",
        }
    return metadata


def _probe_file(lock_path: Path) -> bool:
    """True when the OS lock on this file is currently held by someone."""

    try:
        handle = lock_path.open("r+b")
    except OSError:
        return True  # açılamıyorsa fail-closed: tutuluyor say
    acquired = _try_lock(handle)
    if acquired:
        _unlock(handle)
    handle.close()
    return not acquired


def list_held() -> list[dict[str, object]]:
    """Best-effort inventory of currently held project locks (for the panel)."""

    rows: list[dict[str, object]] = []
    directory = lock_dir()
    if not directory.exists():
        return rows
    for lock_path in directory.glob("*.lock"):
        if not _probe_file(lock_path):
            continue
        try:
            raw = lock_path.read_bytes().decode("utf-8", errors="replace").strip()
            metadata = json.loads(raw) if raw else {}
        except (OSError, json.JSONDecodeError):
            metadata = {}
        if not metadata:
            # Windows'ta kendi tuttuğumuz kilidin metadatası okunamayabilir;
            # bu sürecin sahiplik tablosundan eşleştir.
            for project_path, owner in list(_OWNERS.items()):
                try:
                    if lock_file(project_path) == lock_path:
                        metadata = {"mission_id": owner, "pid": os.getpid()}
                        break
                except OSError:  # pragma: no cover
                    continue
        if not metadata:
            metadata = {"mission_id": "unknown-owner"}
        rows.append({**metadata, "lock_file": str(lock_path)})
    return rows


def own_holds() -> list[dict[str, object]]:
    return [
        {"project": path, "mission_id": mission_id}
        for path, mission_id in _OWNERS.items()
    ]


def owned_by(path: str | Path) -> str | None:
    """Mission id of *this process* that holds the lock (None if not ours)."""

    return _OWNERS.get(str(Path(path).resolve()))


def probe(path: str | Path) -> bool:
    """True when the OS lock is currently held by *someone* (any process)."""

    handle = lock_file(path).open("a+b")
    acquired = _try_lock(handle)
    if acquired:
        _unlock(handle)
    handle.close()
    return not acquired


def _read_metadata(path: str | Path) -> dict[str, object]:
    try:
        raw = lock_file(path).read_bytes().decode("utf-8", errors="replace").strip()
        return json.loads(raw) if raw else {}
    except (OSError, json.JSONDecodeError):
        return {}


_HANDLES: dict[str, object] = {}
_OWNERS: dict[str, str] = {}


def reset_for_tests() -> None:
    for key, handle in list(_HANDLES.items()):
        try:
            _unlock(handle)  # type: ignore[arg-type]
            handle.close()  # type: ignore[union-attr]
        except Exception:  # pragma: no cover
            pass
        _HANDLES.pop(key, None)
