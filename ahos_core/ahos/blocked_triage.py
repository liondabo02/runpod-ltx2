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


def qa_detail(value: str | None) -> str:
    """Whitelisted QA failure families; never return raw error content."""
    message = (value or "").casefold()
    families = (
        ("missing_artifact", ("artifact missing", "missing artifact", "kanıt yok",
                              "çıktı eksik", "eksik varlık", "no evidence", "0 dosya")),
        ("test_failure", ("pytest", "test failed", "assertion", "doğrulama başarısız")),
        ("browser_failure", ("browser", "tarayıcı", "dom check")),
        ("identity_or_approval", ("identity", "approval", "onay", "kendi çıktısını")),
        ("media_failure", ("ffprobe", "video", "audio", "animasyon", "medya")),
        ("resource_limit", ("timeout", "timed out", "limit", "maximum")),
    )
    return next((label for label, words in families
                 if any(word in message for word in words)), "other_qa")


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
        columns = {column[1] for column in conn.execute("PRAGMA table_info(missions)")}
        result_column = "result_json" if "result_json" in columns else "NULL"
        blocked = conn.execute(
            f"SELECT last_error,{result_column} FROM missions WHERE status='blocked' "
            "ORDER BY julianday(updated_at) DESC LIMIT ?", (limit,),
        ).fetchall()
        recent = conn.execute(
            "SELECT status,COUNT(*) FROM ("
            "SELECT status FROM missions ORDER BY julianday(updated_at) DESC LIMIT 30"
            ") GROUP BY status"
        ).fetchall()
    finally:
        conn.close()
    categories = Counter(classify_error(value) for value, _ in blocked)
    qa_details = Counter(
        qa_detail(value) for value, _ in blocked
        if classify_error(value) == "qa_rejected"
    )
    step_stages: Counter[str] = Counter()
    step_qa_causes: Counter[str] = Counter()
    for _, raw in blocked:
        if not isinstance(raw, str):
            step_stages["no_result_payload"] += 1
            continue
        try:
            payload = json.loads(raw)
        except (ValueError, TypeError):
            step_stages["invalid_result_payload"] += 1
            continue
        steps = payload.get("steps") if isinstance(payload, dict) else None
        if not isinstance(steps, list) or not steps:
            step_stages["no_steps"] += 1
            continue
        last = steps[-1]
        if not isinstance(last, dict):
            step_stages["invalid_step"] += 1
            continue
        step_stages[str(last.get("stage") or "unknown")] += 1
        qa_summary = last.get("qa_summary")
        if isinstance(qa_summary, str) and qa_summary.strip():
            step_qa_causes[qa_detail(qa_summary)] += 1
        else:
            step_qa_causes["no_qa_summary"] += 1
    return {
        "status_counts": totals,
        "recent_30_counts": dict(recent),
        "blocked_sampled": len(blocked),
        "blocked_reason_categories": dict(categories.most_common()),
        "qa_root_cause_categories": dict(qa_details.most_common()),
        "last_step_stages": dict(step_stages.most_common()),
        "step_qa_detail_categories": dict(step_qa_causes.most_common()),
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
