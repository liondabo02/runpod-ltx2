"""Evidence-first, read-only audit of AHOS completed-mission statuses.

Only aggregated numbers are returned. No raw objective, worker explanation,
potentially sensitive error text, or mission identifiers are disclosed.
"""

from __future__ import annotations

import argparse
import ast
import json
import sqlite3
from collections import Counter
from pathlib import Path


def classify_completed_payload(raw: str | None) -> str:
    """A consistent result is NOT proof of code delivery or independent QA."""
    if not raw:
        return "missing_result"
    try:
        result = json.loads(raw)
    except (TypeError, ValueError):
        return "malformed_result"
    if not isinstance(result, dict):
        return "malformed_result"
    if result.get("status") != "completed":
        return "result_not_completed"
    steps = result.get("steps")
    if not isinstance(steps, list) or not steps:
        return "no_steps"
    if any(not isinstance(s, dict) for s in steps):
        return "malformed_steps"
    if any(s.get("stage") != "completed" for s in steps):
        return "uncompleted_steps"
    if any(not isinstance(s.get("qa_summary"), str) or
           not s["qa_summary"].strip() for s in steps):
        return "no_qa_summary"
    # A narrative QA summary alone is not a trustworthy receipt.
    return "consistent_but_unverified"


def summarize_completed(db_path: str | Path, *, limit: int = 1000) -> dict[str, object]:
    """Inspect recently updated completed rows without changing database state."""
    if not 1 <= limit <= 10000:
        raise ValueError("limit must be in [1, 10000]")
    path = Path(db_path).resolve()
    if not path.is_file():
        raise FileNotFoundError("mission database not found")
    conn = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True, timeout=3)
    try:
        conn.execute("PRAGMA query_only=ON")
        columns = {row[1] for row in conn.execute("PRAGMA table_info(missions)")}
        required = {"status", "result_json", "updated_at"}
        if not required <= columns:
            raise ValueError("unsupported mission table schema")
        total = conn.execute(
            "SELECT COUNT(*) FROM missions WHERE status='completed'"
        ).fetchone()[0]
        rows = conn.execute(
            "SELECT result_json FROM missions WHERE status='completed' "
            "ORDER BY julianday(updated_at) DESC LIMIT ?",
            (limit,),
        ).fetchall()
    finally:
        conn.close()
    classified = Counter(classify_completed_payload(row[0]) for row in rows)
    inconsistent = sum(classified.get(name, 0) for name in (
        "missing_result", "malformed_result", "result_not_completed",
        "no_steps", "malformed_steps", "uncompleted_steps",
    ))
    return {
        "total_completed_status": total,
        "audited": len(rows),
        "not_audited": total - len(rows),
        "payload_categories": dict(sorted(classified.items())),
        "inconsistent": inconsistent,
        "independent_qa_and_artifact_verified": 0,
        "proof_limitation": "row payload alone cannot independently prove QA or artifact delivery",
        "contains_raw_task_data": False,
    }


def find_unsafe_direct_completion_updates(source_dir: str | Path) -> tuple[str, ...]:
    """Find direct SQL marking missions completed outside the lease/QA API."""
    folder = Path(source_dir)
    if not folder.is_dir():
        raise FileNotFoundError("AHOS source directory not found")
    unsafe: list[str] = []
    for path in sorted(folder.glob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
        except (OSError, SyntaxError, UnicodeError) as exc:
            unsafe.append(f"{path.name}:unreadable")
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            normalized = " ".join(node.value.casefold().split())
            if ("update missions set" in normalized
                    and "status" in normalized
                    and ("'completed'" in normalized or '"completed"' in normalized)):
                unsafe.append(f"{path.name}:{node.lineno}")
    return tuple(unsafe)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only completed mission proof audit")
    parser.add_argument("--database", required=True)
    parser.add_argument("--limit", type=int, default=1000)
    args = parser.parse_args(argv)
    try:
        report = summarize_completed(args.database, limit=args.limit)
    except (OSError, sqlite3.Error, ValueError) as exc:
        print(json.dumps({"ok": False, "reason": type(exc).__name__}))
        return 2
    verified_scope = report["inconsistent"] == 0 and report["not_audited"] == 0
    print(json.dumps({"ok": verified_scope, **report}, ensure_ascii=False))
    return 0 if verified_scope else 2


if __name__ == "__main__":
    raise SystemExit(main())
