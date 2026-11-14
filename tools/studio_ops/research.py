"""AHOS Studio Ops - `research` worker: capability scout (no spending).

    python tools/studio_ops/research.py [--evidence OUT.json]

Reads the studio memory, counts every blocked code, and turns each recurring
failure into a prioritised capability proposal. It never installs, downloads or
buys anything: proposals are advisory and need the owner for paid actions.
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

# known remediation for codes we already understand; anything else stays "unknown"
KNOWN = {
    "SHA_MISMATCH": ("data", "re-download the dependency and compare hashes before use", 0),
    "SHA_MISSING": ("data", "require a 64-hex sha256 in the dependency record", 0),
    "LICENSE_UNVERIFIED": ("security", "record license_status in the upstream artifact", 0),
    "DEPENDENCY_MISSING": ("data", "check the lease payload carries the artifact path", 0),
    "DEPENDENCY_UNMATCHED": ("data", "add character_id to the dependency record", 0),
    "STALE_ARTIFACT": ("software", "clear the stage folder before rebuilding", 0),
    "RIG_TOO_SMALL": ("software", "reject rigs with <10 bones or <5 shape keys", 0),
    "ANIMATION_FAILED": ("software", "inspect the animation log, keep repair rounds <= 2", 0),
    "TTS_FAILED": ("ai-platform", "check the TTS endpoint or switch to a local engine", 0),
    "TTS_MISSING": ("ai-platform", "install edge-tts or register a local TTS", 0),
    "LIPSYNC_GAP": ("software", "tune the viseme heuristic for long pauses", 0),
    "LIPSYNC_TAIL": ("software", "measure the tail against speech end, not file end", 0),
    "MODEL_MISSING": ("ai-platform", "run the mesh stage or place the model in the library", 0),
    "VOICE_DEPENDENCY_REQUIRED": ("creative", "wire the voice stage before lipsync", 0),
}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence")
    ns = parser.parse_args(argv)

    counts, workers = Counter(), Counter()
    if MEMORY.is_dir():
        for path in MEMORY.glob("*.jsonl"):
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                for code in row.get("blocked_codes") or []:
                    counts[code] += 1
                    workers[code] = workers[code]  # keep counter simple
    proposals = []
    for code, hits in counts.most_common():
        department, action, cost = KNOWN.get(code, ("research", "investigate manually", 0))
        proposals.append({"code": code, "hits": hits, "department": department,
                          "proposal": action, "cost_eur": cost,
                          "status": "known" if code in KNOWN else "unknown"})
    report = {
        "schema": "ahos.capability-proposals.v1",
        "blocked_codes": dict(counts),
        "proposals": proposals,
        "status": "PASSED" if proposals else "EMPTY",
        "policy": "advisory only - no install, download or spending is performed here",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    if ns.evidence:
        Path(ns.evidence).parent.mkdir(parents=True, exist_ok=True)
        Path(ns.evidence).write_text(json.dumps(report, indent=2, ensure_ascii=False),
                                     encoding="utf-8")
    for item in proposals:
        print("  %-24s x%d -> %s: %s" % (item["code"], item["hits"],
                                        item["department"], item["proposal"]))
    print("RESEARCH_%s proposals=%d unknown=%d"
          % (report["status"], len(proposals),
             sum(1 for p in proposals if p["status"] == "unknown")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
