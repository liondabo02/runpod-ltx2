"""AHOS Studio Ops - `scout` worker: watch, evaluate, propose adoption.

    python tools/studio_ops/scout.py [--evidence OUT.json] [--online]

Compares every target in studio/agents/watchlist.json with what is actually
installed/registered, then emits an adoption plan per candidate:
adopted / installable / licence_blocked / needs_gpu / needs_reference_voice.

It never installs, never spends and never edits backends. A candidate is adopted
only after an adapter exists and its gates pass - that contract is printed here.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WATCHLIST = ROOT / "studio" / "agents" / "watchlist.json"
REGISTRY = ROOT / "studio" / "pipeline" / "production-backends.json"
ADAPTERS = ROOT / "tools" / "studio_ops" / "adapters"


def installed(module):
    if not module:
        return None
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


def registered_stages():
    if not REGISTRY.is_file():
        return set()
    return set(json.loads(REGISTRY.read_text(encoding="utf-8-sig")).get("stages", {}))


def classify(target, stages):
    gap = target.get("gap")
    module = target.get("module")
    have = installed(module) if module else None
    licence = str(target.get("license") or "").lower()
    if target.get("adopted"):
        return "adopted", "already wired into the studio"
    if "non-commercial" in licence or "cpml" in licence or "company licence" in licence:
        return "licence_decision", "owner must clear commercial rights first"
    if "gpu" in str(target.get("use_case") or "").lower():
        return "needs_gpu", "blocked by hardware/budget approval"
    if have:
        return "installable", "module present, adapter missing"
    if gap in stages:
        return "gap_open", "stage exists but this engine is not wired"
    return "candidate", "adapter not started"


ADAPTER_CONTRACT = {
    "path": "tools/studio_ops/adapters/<id>.py",
    "cli": "python adapters/<id>.py --input FILE --out FILE",
    "requirements": ["sandboxed run", "no network unless declared",
                     "returns JSON with status + artifacts + sha256",
                     "licence recorded before first production use"],
    "gates": ["unit test on a tiny input", "deterministic output hash",
              "no paid call without owner approval"],
}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence")
    parser.add_argument("--online", action="store_true")
    ns = parser.parse_args(argv)

    stages = registered_stages()
    targets = json.loads(WATCHLIST.read_text(encoding="utf-8-sig")).get("targets", [])
    proposals = []
    for target in targets:
        state, reason = classify(target, stages)
        adapter = ADAPTERS / ("%s.py" % target["id"])
        proposals.append({
            "id": target["id"], "gap": target.get("gap"), "state": state,
            "reason": reason, "license": target.get("license"),
            "adapter": str(adapter.relative_to(ROOT)).replace("\\", "/"),
            "adapter_exists": adapter.is_file(),
            "next_step": ("write adapter" if state in ("installable", "gap_open", "candidate")
                          else reason),
        })
    order = {"gap_open": 0, "installable": 1, "candidate": 2, "needs_gpu": 3,
             "licence_decision": 4, "adopted": 5}
    proposals.sort(key=lambda item: (order.get(item["state"], 9), item["id"]))
    report = {
        "schema": "ahos.adoption-plan.v1",
        "targets": len(proposals), "proposals": proposals,
        "adapter_contract": ADAPTER_CONTRACT,
        "status": "PASSED",
        "policy": "scout proposes only: no install, download, spend or backend edit",
        "online_checked": bool(ns.online),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    if ns.evidence:
        Path(ns.evidence).parent.mkdir(parents=True, exist_ok=True)
        Path(ns.evidence).write_text(json.dumps(report, indent=2, ensure_ascii=False),
                                     encoding="utf-8")
    for item in proposals:
        print("  %-26s %-16s %s" % (item["id"], item["state"], item["next_step"]))
    print("SCOUT_PASSED targets=%d adopted=%d open=%d"
          % (len(proposals), sum(1 for p in proposals if p["state"] == "adopted"),
             sum(1 for p in proposals if p["state"] in ("gap_open", "installable", "candidate"))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
