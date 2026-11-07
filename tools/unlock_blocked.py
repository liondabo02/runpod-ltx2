"""Bayat kilitli / panosu bozuk engelli gorevleri guvenle yeniden kuyruga alir.

Varsayilan olarak yalnizca *kuyruk kilitli* engelli gorevleri secer ve kuru
calisir. `--include-board` ile, gorev panosu **su anda gecerliyse**, panosu
okunamadigi icin engellenen gorevler de tek seferlik yeni kimlikle denenir.
Eski satirlar silinmez; hicbir gorev dogrudan "completed" yapilmaz.
"""
import json, sqlite3, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "ahos_core"
RUNTIME = CORE / "runtime"
sys.path.insert(0, str(CORE))


def main(limit: int = 40, *, apply: bool = False, include_board: bool = False,
         match: str = "") -> int:
    """Recover *only* verified queue-state cases; preview by default.

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

    try:
        report = reopen_blocked(RUNTIME, limit=max(0, limit), dry_run=not apply,
                                include_board_schema=include_board, match=match)
    except ValueError as exc:
        print(f"BLOCKED: {exc}")
        return 2

    by_class: dict[str, int] = {}
    for row in report["planned"]:
        by_class[row["class"]] = by_class.get(row["class"], 0) + 1
    print(json.dumps({
        "dry_run": not apply,
        "candidates": report["candidates"],
        "by_class": by_class,
        "planned": [{"old": row["old"], "new": row["new"],
                     "class": row["class"]} for row in report["planned"]],
        "skipped_recovered": report.get("skipped_recovered") or [],
        "moved_items": report["moved_items"],
    }, ensure_ascii=False))
    print("No missions were marked complete; unrecoverable blocks remain blocked.")
    return 0


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Safe queue-state recovery; dry-run by default.")
    parser.add_argument("limit", nargs="?", type=int, default=40)
    parser.add_argument("--apply", action="store_true",
                        help="create fresh retry IDs for verified queue-state failures only")
    parser.add_argument("--include-board", action="store_true",
                        help="also retry missions blocked by an invalid taskboard, only if it now validates")
    parser.add_argument("--match", default="",
                        help="only missions whose id/objective contains this text")
    args = parser.parse_args()
    raise SystemExit(main(args.limit, apply=args.apply,
                          include_board=args.include_board, match=args.match))
