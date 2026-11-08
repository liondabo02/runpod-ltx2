"""Read-only completion wave telemetry; no task texts, errors or IDs."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


def wave(db: str | Path) -> dict[str, object]:
    path = Path(db).resolve()
    if not path.is_file():
        raise FileNotFoundError("mission database not found")
    con = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True, timeout=4)
    try:
        con.execute("PRAGMA query_only=ON")
        by_status = con.execute(
            "SELECT status, COUNT(*) FROM missions GROUP BY status"
        ).fetchall()
        no_result_updates = con.execute(
            "SELECT substr(updated_at,1,16),count(*) FROM missions "
            "WHERE status='completed' AND (result_json IS NULL OR trim(result_json)='') "
            "GROUP BY substr(updated_at,1,16) ORDER BY count(*) DESC LIMIT 12"
        ).fetchall()
        last_updates = con.execute(
            "SELECT substr(updated_at,1,16),count(*) FROM missions "
            "WHERE status='completed' "
            "GROUP BY substr(updated_at,1,16) ORDER BY julianday(updated_at) DESC LIMIT 12"
        ).fetchall()
        by_hour = con.execute(
            "SELECT substr(updated_at,1,13),COUNT(*) FROM missions "
            "WHERE status='completed' AND (result_json IS NULL OR trim(result_json)='') "
            "GROUP BY substr(updated_at,1,13) ORDER BY COUNT(*) DESC LIMIT 8"
        ).fetchall()
    finally:
        con.close()
    return {
        "status_counts": dict(by_status),
        "missing_result_top_update_minutes": no_result_updates,
        "latest_completed_update_minutes": last_updates,
        "missing_result_by_hour": by_hour,
        "no_task_content_emitted": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True)
    args = parser.parse_args()
    print(json.dumps(wave(args.database), ensure_ascii=False))


if __name__ == "__main__":
    main()
