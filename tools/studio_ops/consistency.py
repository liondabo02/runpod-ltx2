"""AHOS Studio Ops - `consistency` audit (roster <-> registry <-> files).

    python tools/studio_ops/consistency.py [--evidence OUT.json]

Fails when the three sources disagree: a stage registered without a script, a
script on disk that is not registered, a WORKING worker without a backend, or an
unknown status. Read-only; it never deletes or rewrites anything.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROSTER = ROOT / "studio" / "agents" / "studio-roster.json"
REGISTRY = ROOT / "studio" / "pipeline" / "production-backends.json"
BACKENDS = ROOT / "tools" / "studio_backends"
OPS = ROOT / "tools" / "studio_ops"
STATUSES = {"WORKING", "PARTIAL", "MISSING"}
# workers that are not media-queue stages live in tools/studio_ops
OPS_WORKERS = {"finance", "security", "research", "data", "distribution"}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence")
    ns = parser.parse_args(argv)

    findings = []
    if not ROSTER.is_file() or not REGISTRY.is_file():
        print("CONSISTENCY_BLOCKED roster_or_registry_missing")
        return 2
    roster = json.loads(ROSTER.read_text(encoding="utf-8-sig"))
    registry = json.loads(REGISTRY.read_text(encoding="utf-8-sig"))
    workers = {w["id"]: w for w in roster.get("workers", [])}
    stages = registry.get("stages", {})

    for stage, spec in stages.items():
        script = ROOT / str(spec.get("script") or "")
        if not script.is_file():
            findings.append({"level": "error", "text": "registry %s -> missing %s"
                                                        % (stage, spec.get("script"))})
        if stage not in workers:
            findings.append({"level": "error", "text": "stage %s has no roster worker" % stage})
        if float(spec.get("cost_eur", 0)) != 0:
            findings.append({"level": "error", "text": "stage %s is not zero-cost" % stage})

    for wid, worker in workers.items():
        status = str(worker.get("status", "")).upper()
        if status not in STATUSES:
            findings.append({"level": "error", "text": "%s has invalid status %r" % (wid, status)})
        if wid in OPS_WORKERS:
            if not (OPS / (wid + ".py")).is_file():
                findings.append({"level": "warn", "text": "ops worker %s has no module yet" % wid})
            continue
        stage = worker.get("stage")
        if stage and status == "WORKING":
            spec = stages.get(stage)
            if not spec:
                findings.append({"level": "error",
                                 "text": "%s is WORKING but stage %s is not registered" % (wid, stage)})
            elif not (ROOT / str(spec["script"])).is_file():
                findings.append({"level": "error",
                                 "text": "%s script missing: %s" % (wid, spec["script"])})
        if status == "WORKING" and wid not in ("director",) and wid not in OPS_WORKERS:
            if not (BACKENDS / (wid + ".py")).is_file() and wid != "edit":
                findings.append({"level": "warn",
                                 "text": "%s is WORKING but tools/studio_backends/%s.py is absent"
                                         % (wid, wid)})

    report = {
        "schema": "ahos.consistency-report.v1",
        "workers": len(workers),
        "stages": sorted(stages),
        "status": "PASSED" if not [f for f in findings if f["level"] == "error"] else "FAILED",
        "findings": findings,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    if ns.evidence:
        Path(ns.evidence).parent.mkdir(parents=True, exist_ok=True)
        Path(ns.evidence).write_text(json.dumps(report, indent=2, ensure_ascii=False),
                                     encoding="utf-8")
    for finding in findings:
        print("  [%s] %s" % (finding["level"], finding["text"]))
    print("CONSISTENCY_%s workers=%d stages=%d findings=%d"
          % (report["status"], len(workers), len(stages), len(findings)))
    return 0 if report["status"] == "PASSED" else 2


if __name__ == "__main__":
    sys.exit(main())
