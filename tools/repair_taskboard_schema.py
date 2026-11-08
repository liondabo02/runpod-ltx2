"""Safely migrate only a known empty legacy taskboard ({}).

The original bytes are saved under an exclusive backup name. Unknown or
nonempty payloads are never rewritten. Coordinate using TaskBoard's OS lock.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ahos_core"))


def migrate(path: str | Path, *, apply: bool = False) -> dict:
    from ahos.taskboard import TaskBoard, TaskBoardError

    target = Path(path)
    if not target.is_file():
        return {"status": "missing", "changed": False}
    board = TaskBoard(target)
    with board.lock_path.open("a+b") as handle:
        deadline = time.monotonic() + board.lock_timeout
        while not board._try_lock(handle):
            if time.monotonic() > deadline:
                raise TaskBoardError("board lock timeout; no changes made")
            time.sleep(0.02)
        try:
            original = target.read_bytes()
            try:
                parsed = json.loads(original.decode("utf-8"))
            except (UnicodeError, ValueError):
                return {"status": "unknown-invalid", "changed": False}
            if isinstance(parsed, dict) and isinstance(parsed.get("tasks"), list):
                board._load()  # verify each row and duplicate ids
                return {"status": "already-valid", "changed": False}
            if parsed != {}:
                return {"status": "unknown-invalid", "changed": False}
            if not apply:
                return {"status": "legacy-empty-preview", "changed": False}
            suffix = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup = target.with_name(target.name + f".backup-{suffix}-{uuid.uuid4().hex[:8]}")
            with backup.open("xb") as out:
                out.write(original)
                out.flush()
                os.fsync(out.fileno())
            temporary = target.with_name(target.name + f".repair-{uuid.uuid4().hex}.tmp")
            try:
                with temporary.open("xb") as out:
                    out.write(json.dumps({
                        "version": 1, "updated_at": datetime.now(timezone.utc).isoformat(),
                        "tasks": [],
                    }, ensure_ascii=False, indent=2).encode("utf-8"))
                    out.flush()
                    os.fsync(out.fileno())
                if target.read_bytes() != original:
                    return {"status": "concurrent-edit-aborted", "changed": False, "backup": str(backup)}
                os.replace(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)
            board._load()
            return {"status": "migrated", "changed": True, "backup": str(backup)}
        finally:
            board._unlock(handle)


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate only empty legacy {} taskboard.")
    parser.add_argument("path", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    result = migrate(args.path, apply=args.apply)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] not in {"unknown-invalid", "concurrent-edit-aborted"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
