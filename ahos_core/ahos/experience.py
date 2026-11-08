"""Verified experience: what actually worked, not just what documents said.

Documents give *rules* (skills). Missions give *evidence*: objective, the method
used, whether the project gate passed, how many files changed and what failed.
This module stores that evidence append-only and retrieves similar past missions
so the next attempt starts from what already worked instead of repeating a
failed method.
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

PATH = "knowledge/experience.jsonl"


def _path(runtime_dir: str | Path) -> Path:
    return Path(runtime_dir) / PATH


def record(
    runtime_dir: str | Path,
    *,
    objective: str,
    department: str,
    mission_id: str = "",
    success: bool,
    changed_files: int = 0,
    method: str = "",
    blocker: str = "",
    cost_usd: float = 0.0,
) -> None:
    path = _path(runtime_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "objective": objective[:200],
        "department": department,
        "mission_id": mission_id[:120],
        "success": bool(success),
        "changed_files": int(changed_files or 0),
        "method": method[:300],
        "blocker": blocker[:300],
        "cost_usd": round(float(cost_usd or 0.0), 6),
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def rows(runtime_dir: str | Path) -> list[dict]:
    path = _path(runtime_dir)
    if not path.is_file():
        return []
    result: list[dict] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            result.append(payload)
    return result


def _terms(text: str) -> set[str]:
    folded = (
        text.casefold()
        .replace("ı", "i").replace("ş", "s").replace("ğ", "g")
        .replace("ü", "u").replace("ö", "o").replace("ç", "c").replace("_", " ")
    )
    return {word for word in re.findall(r"[a-z0-9]{3,}", folded)}


def similar(runtime_dir: str | Path, objective: str, limit: int = 2) -> list[dict]:
    """Past missions with the closest objective, success first."""

    terms = _terms(objective)
    if not terms:
        return []
    scored: list[tuple[float, dict]] = []
    for row in rows(runtime_dir):
        overlap = len(terms & _terms(str(row.get("objective") or "")))
        if not overlap:
            continue
        score = overlap / (len(terms) + 1)
        scored.append((score, row))
    # Aynı benzerlikte başarılı deneyim önce gelir: kanıtlanmış yolu tekrar kullan.
    scored.sort(key=lambda item: (bool(item[1].get("success")), item[0]), reverse=True)
    return [row for _score, row in scored[:limit]]


def context(runtime_dir: str | Path, objective: str, limit: int = 2) -> str:
    """Prompt block: what worked and what failed before, with evidence."""

    hits = similar(runtime_dir, objective, limit)
    if not hits:
        return ""
    lines = ["Geçmiş doğrulanmış deneyim (kanıtla; aynı başarısız yöntemi tekrarlama):"]
    for row in hits:
        verdict = "BAŞARILI" if row.get("success") else "BAŞARISIZ"
        line = f"- [{verdict}] {row.get('objective')} · {row.get('changed_files')} dosya"
        if row.get("method"):
            line += f" · yöntem: {row['method']}"
        if row.get("blocker"):
            line += f" · engel: {row['blocker']}"
        lines.append(line)
    return "\n".join(lines)


def summary(runtime_dir: str | Path) -> dict:
    rows_list = rows(runtime_dir)
    success = sum(1 for row in rows_list if row.get("success"))
    methods: dict[str, int] = {}
    for row in rows_list:
        key = str(row.get("method") or "")[:80]
        if key:
            methods[key] = methods.get(key, 0) + 1
    repeated = sorted(methods.items(), key=lambda item: item[1], reverse=True)[:3]
    return {
        "records": len(rows_list),
        "success": success,
        "rate": round(success / len(rows_list), 3) if rows_list else 0.0,
        "repeated_methods": repeated,
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
    print(summary(runtime))
    for row in rows(runtime)[-5:]:
        verdict = "ok" if row.get("success") else "fail"
        print(f"  {row['at'][11:19]} {verdict} · {row['objective'][:60]} · {row.get('method')[:50]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
