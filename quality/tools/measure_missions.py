"""Measure the worker on a list of objectives and record honest metrics.

Usage:
    python quality/tools/measure_missions.py "hedef 1" "hedef 2" ...

Each mission runs through the real owner console (queue, locks, QA, evidence).
One JSON line per mission is appended to quality/evidence/mission-metrics.jsonl
so the numbers survive restarts and can be compared over time.
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ahos_core"))

from ahos.daemon import _load_model_env  # noqa: E402
from ahos.owner_console import build_default_console  # noqa: E402

METRICS = ROOT / "quality" / "evidence" / "mission-metrics.jsonl"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    objectives = [item for item in sys.argv[1:] if item.strip()]
    if not objectives:
        print("kullanÄ±m: measure_missions.py \"hedef\" ...")
        return 2

    runtime = ROOT / "ahos_core" / "runtime"
    _load_model_env(runtime)
    console = build_default_console(runtime)

    results: list[dict] = []
    for objective in objectives:
        started = time.time()
        result = console.handle(objective)
        elapsed = round(time.time() - started, 1)
        changed = 0
        evidence_ok = False
        steps = 0
        if result.mission is not None:
            steps = len(result.mission.steps)
            for step in result.mission.steps:
                summary = str(getattr(step, "worker_summary", "") or "")
                match = re.search(r"(\d+)\s+dosya", summary)
                if match:
                    changed = int(match.group(1))
                    evidence_ok = changed > 0
        row = {
            "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "objective": objective,
            "status": result.status,
            "seconds": elapsed,
            "steps": steps,
            "changed_files": changed,
            "evidence_ok": evidence_ok,
            "message": (result.message or "")[:200],
        }
        results.append(row)
        METRICS.parent.mkdir(parents=True, exist_ok=True)
        with METRICS.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"[{row['status']}] {elapsed}s Â· {objective[:70]} Â· {row['message'][:90]}")

    total = len(results)
    routed = sum(1 for row in results if row["status"] == "routed")
    delivered = sum(1 for row in results if row["evidence_ok"])
    print("\nÃ¶zet:")
    print(f"  gÃ¶rev: {total}")
    print(f"  tamamlanan: {routed} ({routed / total:.0%})")
    print(f"  kanÄ±tlÄ± teslimat: {delivered} ({delivered / total:.0%})")
    print(f"  ortalama sÃ¼re: {sum(r['seconds'] for r in results) / total:.1f} sn")
    print(f"  kayÄ±t: {METRICS}")
    return 0 if routed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())

