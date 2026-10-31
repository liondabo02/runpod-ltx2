"""Read-only, secret-free diagnosis of AHOS blocked missions.

A blocked/cancelled mission is never changed by this command. Only aggregate
counts and normalized error categories are returned; no raw prompts or errors.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from pathlib import Path

CATEGORIES = (
    ("model_unavailable", ("model_unavailable", "model not found", "no model available")),
    ("rate_limit", ("rate limit", "rate_limit", "429", "too many requests")),
    ("provider_timeout", ("timed out", "timeout", "connection refused", "unreachable")),
    ("qa_rejected", ("qa failed", "qa_rejected", "acceptance", "test failed", "verification failed")),
    ("missing_executor", ("no executor", "executor unavailable", "not configured")),
    ("budget", ("budget", "quota", "credit exhausted", "insufficient funds")),
    ("permission", ("permission denied", "not authorized", "approval required")),
    ("worktree", ("worktree", "merge conflict", "file lock")),
)


def classify_error(value: str | None) -> str:
    message = (value or "").casefold()
    if not message.strip():
        return "no_reason_recorded"
    for label, needles in CATEGORIES:
        if any(needle in message for needle in needles):
            return label
    return "other"


def summarize(db_path: str | Path, *, limit: int = 500) -> dict[str, object]:
    if not 1 <= limit <= 5000:
        raise ValueError("limit must be between 1 and 5000")
    db = Path(db_path).resolve()
    if not db.is_file():
        raise FileNotFoundError("mission database missing")

    conn = sqlite3.connect(f"{db.as_uri()}?mode=ro", uri=True, timeout=2)
    try:
        conn.execute("PRAGMA query_only=ON")
        totals = dict(conn.execute(
            "SELECT status,COUNT(*) FROM missions GROUP BY status"
        ).fetchall())
        blocked = conn.execute(
            "SELECT last_error FROM missions WHERE status='blocked' "
            "ORDER BY julianday(updated_at) DESC LIMIT ?", (limit,),
        ).fetchall()
        recent = conn.execute(
            "SELECT status,COUNT(*) FROM ("
            "SELECT status FROM missions ORDER BY julianday(updated_at) DESC LIMIT 30"
            ") GROUP BY status"
        ).fetchall()
    finally:
        conn.close()
    categories = Counter(classify_error(value) for (value,) in blocked)
    return {
        "status_counts": totals,
        "recent_30_counts": dict(recent),
        "blocked_sampled": len(blocked),
        "blocked_reason_categories": dict(categories.most_common()),
        "contains_raw_error_text": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only AHOS blocked mission triage")
    parser.add_argument("--database", required=True)
    parser.add_argument("--limit", type=int, default=500)
    args = parser.parse_args(argv)
    try:
        report = summarize(args.database, limit=args.limit)
    except (OSError, sqlite3.Error, ValueError) as exc:
        print(json.dumps({"ok": False, "reason": type(exc).__name__}))
        return 2
    print(json.dumps({"ok": True, **report}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
