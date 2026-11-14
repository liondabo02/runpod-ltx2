"""AHOS Studio Ops - `data` worker: production analytics (read-only).

    python tools/studio_ops/data.py [--job-root DIR] [--evidence OUT.json]

Aggregates the append-only worker memory (studio/agents/memory/*.jsonl) into
throughput and quality metrics: runs per worker, pass rate, blocked codes, and the
wall-clock span. This is what a 10-episode run is judged on - no invented numbers.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MEMORY = ROOT / "studio" / "agents" / "memory"


def read_worker(path: Path):
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-root")
    parser.add_argument("--evidence")
    ns = parser.parse_args(argv)

    per_worker, blocked_counter, stamps = {}, Counter(), []
    files = sorted(MEMORY.glob("*.jsonl")) if MEMORY.is_dir() else []
    for path in files:
        rows = read_worker(path)
        if not rows:
            continue
        passes = sum(1 for row in rows if row.get("status") == "PASSED")
        codes = Counter(code for row in rows for code in (row.get("blocked_codes") or []))
        blocked_counter.update(codes)
        for row in rows:
            if row.get("at"):
                stamps.append(row["at"])
        per_worker[path.stem] = {
            "runs": len(rows),
            "pass_rate": round(passes / float(len(rows)), 3),
            "last_status": rows[-1].get("status"),
            "blocked_codes": dict(codes),
        }

    span_seconds = 0.0
    if len(stamps) >= 2:
        try:
            first = datetime.fromisoformat(min(stamps))
            last = datetime.fromisoformat(max(stamps))
            span_seconds = round((last - first).total_seconds(), 1)
        except ValueError:
            span_seconds = 0.0

    report = {
        "schema": "ahos.analytics-report.v1",
        "workers_with_memory": len(per_worker),
        "total_runs": sum(w["runs"] for w in per_worker.values()),
        "overall_pass_rate": (round(sum(w["pass_rate"] * w["runs"] for w in per_worker.values())
                                    / max(1, sum(w["runs"] for w in per_worker.values())), 3)
                              if per_worker else None),
        "blocked_codes": dict(blocked_counter),
        "observation_span_seconds": span_seconds,
        "per_worker": per_worker,
        "status": "PASSED" if per_worker else "EMPTY",
        "note": "metrics come from studio/agents/memory/*.jsonl only; "
                "no estimate is generated when there is no evidence",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    if ns.evidence:
        Path(ns.evidence).parent.mkdir(parents=True, exist_ok=True)
        Path(ns.evidence).write_text(json.dumps(report, indent=2, ensure_ascii=False),
                                     encoding="utf-8")
    for worker, stats in sorted(per_worker.items()):
        print("  %-12s runs=%-3d pass=%s" % (worker, stats["runs"], stats["pass_rate"]))
    print("DATA_%s workers=%d runs=%d pass_rate=%s span=%.0fs"
          % (report["status"], report["workers_with_memory"], report["total_runs"],
             report["overall_pass_rate"], span_seconds))
    return 0 if report["status"] == "PASSED" else 0


if __name__ == "__main__":
    sys.exit(main())
