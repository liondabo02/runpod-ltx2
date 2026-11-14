"""AHOS Studio Ops - register the studio's workers as holding departments.

    python tools/studio_ops/register_departments.py [--runtime DIR] [--dry-run]

The holding office (ahos_core/ahos/agent_office.py) renders whatever is listed in
runtime/departments.json and groups live missions by `primary_department`. This
script merges the 15 studio workers into that file so they appear as staff, with
their stage, role, status and capabilities - the office then shows them working.

It only adds/updates entries whose ids start with "studio_"; other departments are
left untouched.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROSTER = ROOT / "studio" / "agents" / "studio-roster.json"
PREFIX = "studio_"


def load(path: Path):
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except ValueError:
        return []
    raw = payload.get("departments") if isinstance(payload, dict) else payload
    return raw if isinstance(raw, list) else []


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime")
    parser.add_argument("--dry-run", action="store_true")
    ns = parser.parse_args(argv)

    runtime = Path(ns.runtime).resolve() if ns.runtime else (ROOT / "runtime")
    target = runtime / "departments.json"
    roster = json.loads(ROSTER.read_text(encoding="utf-8-sig")).get("workers", [])

    existing = [d for d in load(target) if not str(d.get("id") or d.get("name") or "").startswith(PREFIX)]
    added, updated = [], []
    for worker in roster:
        entry = {
            "id": PREFIX + worker["id"],
            "name": PREFIX + worker["id"],
            "label": worker.get("role"),
            "department": "studio",
            "stage": worker.get("stage"),
            "status": "active" if worker.get("status") == "WORKING" else "paused",
            "capabilities": [worker.get("stage")] if worker.get("stage") else [],
            "engine": (worker.get("engine") or {}).get("runtime"),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        previous = next((d for d in existing if d.get("id") == entry["id"]), None)
        if previous:
            previous.update(entry)
            updated.append(entry["id"])
        else:
            existing.append(entry)
            added.append(entry["id"])

    payload = {"departments": existing,
               "schema": "ahos.departments.v1",
               "updated_at": datetime.now(timezone.utc).isoformat()}
    if not ns.dry_run:
        runtime.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print("DEPARTMENTS_%s total=%d added=%d updated=%d -> %s"
          % ("DRY" if ns.dry_run else "SYNCED", len(existing), len(added), len(updated), target))
    return 0


if __name__ == "__main__":
    sys.exit(main())
