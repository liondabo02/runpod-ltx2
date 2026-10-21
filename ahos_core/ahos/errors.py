"""One append-only error journal for every AHOS process.

Panels, the daemon and CLIs each used to swallow failures into different logs,
so "what is broken right now" had no single answer. This module writes one
JSONL file with a bounded record size, rotates it when it grows, and can be
read by a CLI or a dashboard without loading the whole history.
"""

from __future__ import annotations

import json
import os
import traceback
from datetime import datetime, timezone
from pathlib import Path

MAX_MESSAGE = 1000
MAX_TRACEBACK = 4000
DEFAULT_MAX_BYTES = 1_000_000


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class ErrorLog:
    """Append-only, size-capped JSONL error journal."""

    def __init__(self, path: str | Path, *, max_bytes: int = DEFAULT_MAX_BYTES) -> None:
        self.path = Path(path)
        self.max_bytes = int(max_bytes)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _rotate_if_needed(self) -> None:
        try:
            size = self.path.stat().st_size
        except OSError:
            return
        if size < self.max_bytes:
            return
        backup = self.path.with_suffix(self.path.suffix + ".1")
        try:
            if backup.exists():
                backup.unlink()
            os.replace(self.path, backup)
        except OSError:  # pragma: no cover - rotation must never break callers
            pass

    def record(
        self,
        source: str,
        error: BaseException | str,
        *,
        mission_id: str = "",
        context: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """Persist one failure and return the stored record."""

        if isinstance(error, BaseException):
            kind = type(error).__name__
            message = str(error)
            trace = "".join(
                traceback.format_exception(type(error), error, error.__traceback__)
            )[-MAX_TRACEBACK:]
        else:
            kind = "Error"
            message = str(error)
            trace = ""
        record: dict[str, object] = {
            "at": _now(),
            "source": source[:120],
            "kind": kind,
            "message": message[:MAX_MESSAGE],
            "mission_id": mission_id[:120],
        }
        if trace:
            record["traceback"] = trace
        if context:
            record["context"] = {
                str(key)[:60]: str(value)[:200] for key, value in context.items()
            }
        self._rotate_if_needed()
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        return record

    def recent(self, limit: int = 20) -> list[dict[str, object]]:
        """Last ``limit`` records, newest last."""

        try:
            lines = self.path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            return []
        rows: list[dict[str, object]] = []
        for line in lines[-max(1, limit) :]:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                rows.append(payload)
        return rows

    def count(self) -> int:
        try:
            return sum(
                1
                for line in self.path.read_text(encoding="utf-8", errors="ignore").splitlines()
                if line.strip()
            )
        except OSError:
            return 0


def default_error_log(runtime_dir: str | Path) -> ErrorLog:
    return ErrorLog(Path(runtime_dir) / "errors.jsonl")


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="ahos-errors",
        description="AHOS hata günlüğü: son kayıtları göster.",
    )
    parser.add_argument("--runtime-dir", default=str(Path.cwd() / "runtime"))
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args(argv)

    log = default_error_log(args.runtime_dir)
    rows = log.recent(args.limit)
    if not rows:
        print("(hata kaydı yok)")
        return 0
    for row in rows:
        mission = f" [{row.get('mission_id')}]" if row.get("mission_id") else ""
        print(
            f"{row.get('at','')} {row.get('source','?')}{mission} "
            f"{row.get('kind','Error')}: {row.get('message','')}"
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
