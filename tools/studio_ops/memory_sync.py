"""AHOS Studio Ops - `memory_sync`: every stage evidence feeds the worker memory.

    python tools/studio_ops/memory_sync.py [--job-root DIR] [--dry-run]

Walks the job folders, finds every stage evidence file and appends one record per
stage to studio/agents/memory/<stage>.jsonl. Records are de-duplicated by the
sha256 of the evidence file, so re-running never inflates the history.

This gives *every* worker a memory even when its backend does not call the memory
module directly - the hook is central instead of per-backend.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MEMORY = ROOT / "studio" / "agents" / "memory"
SKIP = ("qa-report", "finance", "rights", "consistency", "analytics", "adoption",
        "capability", "delivery", "edit-manifest", "scene-manifest")


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def seen_keys(worker: str):
    path = MEMORY / ("%s.jsonl" % worker)
    if not path.is_file():
        return set()
    keys = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            keys.add(json.loads(line).get("evidence_sha"))
        except ValueError:
            continue
    return keys


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-root")
    parser.add_argument("--dry-run", action="store_true")
    ns = parser.parse_args(argv)

    root = Path(ns.job_root).resolve() if ns.job_root else (ROOT / "studio" / "jobs")
    if not root.is_dir():
        print("MEMORY_SYNC_EMPTY no job root")
        return 0

    MEMORY.mkdir(parents=True, exist_ok=True)
    cache, appended, skipped = {}, 0, 0
    for path in sorted(root.rglob("*evidence*.json")):
        if any(token in path.name for token in SKIP):
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except ValueError:
            continue
        stage = payload.get("stage")
        if not stage:
            continue
        key = sha(path)
        if stage not in cache:
            cache[stage] = seen_keys(stage)
        if key in cache[stage]:
            skipped += 1
            continue
        record = {
            "worker_id": stage, "status": payload.get("status"),
            "evidence_sha": key, "evidence": str(path),
            "cast": payload.get("cast_ids"), "cost_eur": payload.get("cost_eur"),
            "artifacts": len(payload.get("artifacts") or []),
            "blocked_codes": [b.get("code") for b in (payload.get("blocked") or [])],
            "at": datetime.now(timezone.utc).isoformat(),
        }
        if not ns.dry_run:
            with (MEMORY / ("%s.jsonl" % stage)).open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        cache[stage].add(key)
        appended += 1

    print("MEMORY_SYNC_%s appended=%d skipped=%d workers=%d%s"
          % ("DRY" if ns.dry_run else "DONE", appended, skipped, len(cache),
             "" if appended or skipped else " (no evidence found)"))
    for stage in sorted(cache):
        path = MEMORY / ("%s.jsonl" % stage)
        runs = len([l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]) \
            if path.is_file() else 0
        print("  %-16s runs=%d" % (stage, runs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
