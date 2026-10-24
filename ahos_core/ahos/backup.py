"""Backup the holding's runtime state; nothing is ever deleted.

Creates ``runtime/backups/runtime-YYYYmmdd-HHMM.zip`` with the mission queue,
state files, knowledge network, brains, companies and ledgers. Keeps the newest
seven archives. The live files are only read.
"""

from __future__ import annotations

import sys
import time
import zipfile
from pathlib import Path

KEEP = 7
INCLUDE = (
    "company-service.db",
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
    "ideas",
    "knowledge",
    "brains",
    "companies",
)


def backup(runtime_dir: str | Path) -> Path | None:
    runtime = Path(runtime_dir)
    if not runtime.is_dir():
        return None
    target_dir = runtime / "backups"
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M")
    archive = target_dir / f"runtime-{stamp}.zip"
    written = 0
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for name in INCLUDE:
            source = runtime / name
            if not source.exists():
                continue
            if source.is_file():
                bundle.write(source, f"runtime/{name}")
                written += 1
                continue
            for path in source.rglob("*"):
                if path.is_file():
                    bundle.write(path, f"runtime/{name}/{path.relative_to(source).as_posix()}")
                    written += 1
    # Yalnız en yeni yedi arşiv kalsın; eski yedekler silinmez, arşivlenir.
    archives = sorted(target_dir.glob("runtime-*.zip"))
    for old in archives[:-KEEP]:
        old.rename(old.with_suffix(".zip.old"))
    print(f"yedek: {archive.name} · {written} dosya · {archive.stat().st_size // 1024} KB")
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
