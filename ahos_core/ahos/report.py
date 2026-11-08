"""One honest status view over the files the holding already writes.

The panel has its own rendering; this module exists for operators, scripts and
future panel code that just needs the facts: is the loop alive, what did it
deliver, what failed, what is queued for a human or another agent.
"""

from __future__ import annotations

import json
from pathlib import Path

from .errors import default_error_log
from .taskboard import TaskBoard

MISSIONS_FILE = "daemon-missions.jsonl"


def _read_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_jsonl(path: Path) -> list[dict]:
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return []
    rows = []
    for line in lines:
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


def collect(runtime_dir: str | Path, *, missions: int = 5, errors: int = 5) -> dict:
    runtime = Path(runtime_dir)

    heartbeat = _read_json(runtime / "daemon-state.json")
    autonomy = _read_json(runtime / "autonomy-state.json")
    scheduler = _read_json(runtime / "auto-scheduler-state.json")
    ledger = _read_jsonl(runtime / MISSIONS_FILE)
    recent = ledger[-missions:] if missions else []
    error_rows = default_error_log(runtime).recent(errors)
    board = TaskBoard(runtime / "taskboard.json").tasks() if (runtime / "taskboard.json").exists() else ()

    from .roster import build_roster

    roster = build_roster(runtime)

    delivered = sum(1 for row in ledger if row.get("changed_files"))
    states: dict[str, int] = {}
    for task in board:
        states[task.state] = states.get(task.state, 0) + 1

    return {
        "daemon": {
            "running": bool(heartbeat),
            "pid": heartbeat.get("pid"),
            "ticks": heartbeat.get("ticks", 0),
            "status": heartbeat.get("status", "not-running"),
            "executor_mode": heartbeat.get("executor_mode", ""),
            "executor_reason": heartbeat.get("executor_reason", ""),
            "no_evidence_streak": heartbeat.get("no_evidence_streak", 0),
        },
        "autonomy": {
            "status": autonomy.get("status", "unknown"),
            "executed": autonomy.get("executed", 0),
            "failed": autonomy.get("failed", 0),
            "last_mission": autonomy.get("last_mission", ""),
        },
        "scheduler": {
            "missions_this_hour": scheduler.get("missions_this_hour", 0),
            "missions_total": scheduler.get("missions_total", 0),
            "status": scheduler.get("status", ""),
        },
        "delivery": {
            "recorded": len(ledger),
            "with_changes": delivered,
            "recent": recent,
            "models": {},
        },
        "errors": error_rows,
        "board": {"counts": states, "open": len(board) - states.get("done", 0)},
        "agents": {
            "total": roster["summary"]["total"],
            "by_kind": roster["summary"]["by_kind"],
        },
    }


def render(report: dict) -> str:
    daemon = report["daemon"]
    autonomy = report["autonomy"]
    scheduler = report["scheduler"]
    delivery = report["delivery"]
    lines = [
        "AHOS DURUM",
        f"  daemon      : {daemon['status']} (pid {daemon['pid']}, {daemon['ticks']} tick)"
        f" · mod={daemon['executor_mode'] or '-'}",
        f"  otonomi     : {autonomy['status']} · {autonomy['executed']} tamam, {autonomy['failed']} hata",
        f"  saat kotası : {scheduler['missions_this_hour']} / toplam {scheduler['missions_total']}"
        f" ({scheduler['status'] or '-'})",
        f"  teslimat    : {delivery['with_changes']}/{delivery['recorded']} görevde dosya değişikliği",
        f"  ajanlar     : {report.get('agents', {}).get('total', 0)} kayıtlı "
        f"({', '.join(f'{k}={v}' for k, v in sorted(report.get('agents', {}).get('by_kind', {}).items()))})",
        f"  pano        : {report['board']['open']} açık görev",
        f"  hata        : {len(report['errors'])} son kayıt",
    ]
    for row in delivery["recent"]:
        changed = row.get("changed_files", 0)
        mark = "✓" if changed else "·"
        mission = str(row.get("mission_id", ""))[-24:]
        lines.append(f"    {mark} {mission} değişen={changed}")
    for row in report["errors"][-3:]:
        lines.append(f"    ! {row.get('source','?')}: {str(row.get('message',''))[:70]}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # pragma: no cover
        pass

    parser = argparse.ArgumentParser(
        prog="ahos-status",
        description="Holding durumunu kalıcı kayıtlardan tek ekranda özetler.",
    )
    parser.add_argument("--runtime-dir", default=str(Path.cwd() / "runtime"))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = collect(args.runtime_dir)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(render(report))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
