"""Skill coverage and usage: is the learned library actually helping?

Two questions matter for a learning system:

1. **Coverage** — for the work the holding does, does a skill card exist?
2. **Usage** — when a card was injected into a prompt, did the mission deliver?

This module answers both from files the holding already writes, and lists the
topics with no coverage so the owner knows what to add next.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from .skills import all_cards, retrieve

USAGE_PATH = "knowledge/skill-usage.jsonl"


def _usage_path(runtime_dir: str | Path) -> Path:
    return Path(runtime_dir) / USAGE_PATH


def log_usage(runtime_dir: str | Path, task: str, cards: list[dict], *, mission: str = "") -> None:
    """Append what was injected; never rewrites history."""

    if not cards:
        return
    path = _usage_path(runtime_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "at": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"),
        "task": task[:200],
        "mission": mission[:120],
        "skills": [str(card.get("skill_id") or "") for card in cards],
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def usage_rows(runtime_dir: str | Path) -> list[dict]:
    path = _usage_path(runtime_dir)
    if not path.is_file():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def coverage(runtime_dir: str | Path, tasks: list[str]) -> dict:
    """Hit rate of the skill library for a list of task titles."""

    rows: list[dict] = []
    hits = 0
    for task in tasks:
        cards = retrieve(runtime_dir, task, limit=3)
        if cards:
            hits += 1
        rows.append(
            {
                "task": task[:160],
                "matched": len(cards),
                "top": str(cards[0].get("rule") or "")[:120] if cards else "",
            }
        )
    total = len(tasks)
    return {
        "tasks": total,
        "with_skill": hits,
        "rate": round(hits / total, 3) if total else 0.0,
        "rows": rows,
    }


def gaps(runtime_dir: str | Path, tasks: list[str]) -> list[str]:
    """Tasks for which the library has nothing: the next documents to add."""

    missing: list[str] = []
    for task in tasks:
        if not retrieve(runtime_dir, task, limit=1):
            missing.append(task[:160])
    return missing


def report(runtime_dir: str | Path, tasks: list[str] | None = None) -> dict:
    runtime = Path(runtime_dir)
    cards = all_cards(runtime)
    rows = usage_rows(runtime)
    used: dict[str, int] = {}
    for row in rows:
        for skill_id in row.get("skills") or []:
            used[skill_id] = used.get(skill_id, 0) + 1
    if tasks is None:
        tasks = [str(row.get("task") or "") for row in rows][-20:]
    coverage_result = coverage(runtime, tasks) if tasks else {"tasks": 0, "rate": 0.0, "rows": []}
    unused = [card for card in cards if str(card.get("skill_id")) not in used]
    return {
        "cards": len(cards),
        "sources": len({card.get("source") for card in cards}),
        "used_cards": len(used),
        "injections": len(rows),
        "coverage_rate": coverage_result["rate"],
        "missing": gaps(runtime, tasks)[:10],
        "unused": len(unused),
    }


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # pragma: no cover
        pass
    args = list(sys.argv[1:] if argv is None else argv)
    runtime = Path("runtime")
    if "--runtime-dir" in args:
        position = args.index("--runtime-dir")
        runtime = Path(args[position + 1])
    tasks: list[str] = []
    if "--tasks" in args:
        position = args.index("--tasks")
        tasks = [line.strip() for line in args[position + 1].split("|") if line.strip()]
    result = report(runtime, tasks or None)
    print(f"beceri: {result['cards']} kart / {result['sources']} kaynak")
    print(f"kullanılan: {result['used_cards']} · enjeksiyon: {result['injections']}")
    print(f"kapsama: %{round(result['coverage_rate'] * 100)}")
    if result["missing"]:
        print("belge eksik konular:")
        for item in result["missing"]:
            print(f"  - {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
