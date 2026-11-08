"""Who works here: a shared roster every agent can consult.

The holding already stores departments, their workers and the reporting lines in
``runtime/departments.json``. This module turns that plus the live runtime files
into a single registry: each agent has an id, a role, its capabilities, who it
reports to and what it has done lately. The planner and the status report read
the same roster, so the organisation is described one way everywhere.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

CAPABILITY_LIMIT = 8


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _capability_names(items) -> list[str]:
    """Capabilities are stored either as strings or as small dicts."""

    names: list[str] = []
    for item in items or ():
        if isinstance(item, dict):
            name = item.get("name") or item.get("capability") or item.get("id")
            if name:
                names.append(str(name))
        elif item:
            names.append(str(item))
    return names[:CAPABILITY_LIMIT]


def _cards_from_book(book: dict) -> tuple[list[dict], list[dict]]:
    agents: list[dict] = []
    edges: list[dict] = []
    departments = book.get("departments")
    if not isinstance(departments, list):
        return agents, edges

    for department in departments:
        if not isinstance(department, dict):
            continue
        department_id = str(department.get("department_id") or "")
        if not department_id:
            continue
        agents.append(
            {
                "id": department_id,
                "kind": "department",
                "name": str(department.get("name") or department_id),
                "capabilities": _capability_names(department.get("capabilities")),
                "status": str(department.get("status") or "active"),
                "reports_to": "holding",
                "metrics": {"mission": str(department.get("mission") or "")[:160]},
            }
        )
        edges.append({"from": department_id, "to": "holding", "kind": "reports_to"})
        for worker in department.get("workers") or ():
            if not isinstance(worker, dict):
                continue
            worker_id = str(worker.get("worker_id") or "")
            if not worker_id:
                continue
            reports_to = str(worker.get("reports_to") or department_id)
            agents.append(
                {
                    "id": worker_id,
                    "kind": "worker",
                    "name": str(worker.get("name") or worker_id),
                    "capabilities": _capability_names(worker.get("capabilities")),
                    "status": "ready",
                    "reports_to": reports_to,
                    "metrics": {
                        "role": str(worker.get("role") or ""),
                        "authority": worker.get("authority_level"),
                        "paid_ai": bool(worker.get("paid_ai_enabled")),
                        "daily_budget_usd": worker.get("daily_budget_usd"),
                    },
                }
            )
            edges.append({"from": worker_id, "to": reports_to, "kind": "reports_to"})
            edges.append({"from": worker_id, "to": department_id, "kind": "member_of"})
    return agents, edges


def _infrastructure_cards(runtime: Path) -> list[dict]:
    cards: list[dict] = []
    heartbeat = _read_json(runtime / "daemon-state.json")
    if heartbeat:
        cards.append(
            {
                "id": "daemon",
                "kind": "infrastructure",
                "name": "Otonomi daemon'u",
                "capabilities": ["schedule", "supervise", "evidence_gate"],
                "status": str(heartbeat.get("status") or "unknown"),
                "reports_to": "holding",
                "metrics": {
                    "pid": heartbeat.get("pid"),
                    "ticks": heartbeat.get("ticks"),
                    "executor_mode": heartbeat.get("executor_mode"),
                    "last_tick_at": heartbeat.get("last_tick_at"),
                },
            }
        )
    autonomy = _read_json(runtime / "autonomy-state.json")
    if autonomy:
        cards.append(
            {
                "id": "autonomy",
                "kind": "infrastructure",
                "name": "Otonomi çalıştırıcısı",
                "capabilities": ["plan_execution", "dedupe", "budget"],
                "status": str(autonomy.get("status") or "unknown"),
                "reports_to": "holding",
                "metrics": {
                    "executed": autonomy.get("executed"),
                    "failed": autonomy.get("failed"),
                    "last_mission": autonomy.get("last_mission"),
                },
            }
        )
    plan = _read_json(runtime / "auto-plan.json")
    if plan:
        objectives = plan.get("objectives")
        cards.append(
            {
                "id": "planner",
                "kind": "infrastructure",
                "name": "Model planlayıcı",
                "capabilities": ["objective_generation", "prioritisation"],
                "status": "ready" if objectives else "exhausted",
                "reports_to": "holding",
                "metrics": {
                    "day": plan.get("day"),
                    "pending": len(objectives) if isinstance(objectives, list) else 0,
                },
            }
        )
    outbox = runtime / "cloud-outbox"
    if outbox.is_dir():
        proposals = sorted(outbox.glob("*.json"))
        cards.append(
            {
                "id": "cloud-worker",
                "kind": "infrastructure",
                "name": "Bulut işçisi",
                "capabilities": ["patch_proposals", "offline_work"],
                "status": "ready",
                "reports_to": "holding",
                "metrics": {"proposals": len(proposals)},
            }
        )
    cards.append(
        {
            "id": "qa",
            "kind": "infrastructure",
            "name": "Kalite kapısı",
            "capabilities": ["asset_audit", "browser_check", "revert"],
            "status": "ready",
            "reports_to": "holding",
            "metrics": {},
        }
    )
    return cards


def build_roster(runtime_dir: str | Path) -> dict:
    runtime = Path(runtime_dir)
    book = _read_json(runtime / "departments.json")
    agents, edges = _cards_from_book(book)
    agents.extend(_infrastructure_cards(runtime))

    seen: set[str] = set()
    unique: list[dict] = []
    for card in agents:
        agent_id = card["id"]
        if agent_id in seen:
            continue
        seen.add(agent_id)
        unique.append(card)

    for card in unique:
        card["peers"] = sorted(other["id"] for other in unique if other["id"] != card["id"])

    by_kind: dict[str, int] = {}
    for card in unique:
        by_kind[card["kind"]] = by_kind.get(card["kind"], 0) + 1

    return {
        "generated_at": _now(),
        "summary": {"total": len(unique), "by_kind": by_kind},
        "agents": unique,
        "edges": edges,
    }


def render(roster: dict) -> str:
    summary = roster.get("summary", {})
    lines = [
        f"AHOS AJAN KAYDI · {summary.get('total', 0)} ajan "
        f"({', '.join(f'{kind}={count}' for kind, count in sorted(summary.get('by_kind', {}).items()))})",
    ]
    for card in roster.get("agents", []):
        capabilities = ", ".join(card.get("capabilities") or ())[:60]
        reports = card.get("reports_to") or "-"
        lines.append(
            f"  [{card['kind']:<14}] {card['id']:<28} {card.get('status', '-'):<10} "
            f"→ {reports:<20} {capabilities}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # pragma: no cover - odd console
        pass
    args = list(sys.argv[1:] if argv is None else argv)
    runtime = Path(
        args[args.index("--runtime-dir") + 1]
        if "--runtime-dir" in args and args.index("--runtime-dir") + 1 < len(args)
        else "runtime"
    )
    roster = build_roster(runtime)
    if "--json" in args:
        print(json.dumps(roster, ensure_ascii=False, indent=2))
        return 0
    print(render(roster))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
