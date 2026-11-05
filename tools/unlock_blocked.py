"""Bayat kilitli engelli gorevleri temizleyip yeniden kuyruga alir."""
import json, sqlite3, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "ahos_core"
RUNTIME = CORE / "runtime"
sys.path.insert(0, str(CORE))


def main(limit: int = 40, *, apply: bool = False) -> int:
    """Recover *only* verified stale lock cases; preview by default.

    A blocked mission may have failed QA, an invalid taskboard schema, or
    irreversible side effects. Never update all blocked SQLite rows, clear
    ownership evidence or rewrite the taskboard as an untyped lock dict.
    """
    from ahos.queue_repair import reopen_blocked

    board_path = RUNTIME / "taskboard.json"
    if board_path.exists():
        from ahos.taskboard import TaskBoard, TaskBoardError
        try:
            TaskBoard(board_path).tasks()  # read-only schema validation
        except TaskBoardError as exc:
            print(f"BLOCKED: taskboard invalid; repair it first: {exc}")
            return 2

    report = reopen_blocked(RUNTIME, limit=max(0, limit), dry_run=not apply)
    print(json.dumps({
        "dry_run": not apply,
        "candidates": report["candidates"],
        "planned": report["planned"],
        "moved_items": report["moved_items"],
    }, ensure_ascii=False))
    print("No missions were marked complete; unrecoverable blocks remain blocked.")
    return 0


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Safe stale-lock recovery; dry-run by default.")
    parser.add_argument("limit", nargs="?", type=int, default=40)
    parser.add_argument("--apply", action="store_true",
                        help="create fresh retry IDs for verified stale-lock failures only")
    args = parser.parse_args()
    raise SystemExit(main(args.limit, apply=args.apply))