"""AHOS Studio Ops - `finance` worker (budget + licence audit, zero cost).

    python tools/studio_ops/finance.py --job-dir DIR [--evidence OUT.json]

Scans every stage evidence in a job folder and reports:
  * total cost_eur against the per-episode ceiling (1.00 EUR)
  * stages that claim a commercial licence without provenance
  * artifacts whose sha256 is missing
It never changes stage results; it is an independent audit, not an approval.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

CEILING_EUR = 1.00
REQUIRED = ("stage", "status", "cost_eur", "commercial_license_verified", "artifacts")


def load_evidences(job: Path):
    rows = []
    for path in sorted(job.rglob("*evidence*.json")):
        if "finance" in path.name or "qa-" in path.name:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except ValueError:
            rows.append({"path": str(path), "parse_error": True})
            continue
        if not isinstance(payload, dict) or "stage" not in payload:
            continue
        payload["_path"] = str(path.relative_to(job)).replace("\\", "/")
        rows.append(payload)
    return rows


def audit(rows):
    findings, total = [], 0.0
    seen = set()
    for row in rows:
        if row.get("parse_error"):
            findings.append({"level": "error", "text": "%s is not valid JSON" % row["path"]})
            continue
        missing = [key for key in REQUIRED if key not in row]
        if missing:
            findings.append({"level": "error",
                             "text": "%s missing %s" % (row.get("_path"), ",".join(missing))})
        stage = str(row.get("stage"))
        seen.add(stage)
        cost = row.get("cost_eur", 0)
        if not isinstance(cost, (int, float)):
            findings.append({"level": "error", "text": "%s cost_eur is not numeric" % stage})
            cost = 0
        total += float(cost)
        if row.get("commercial_license_verified") is True:
            basis = str(row.get("license_basis") or "")
            if len(basis) < 8:
                findings.append({"level": "error",
                                 "text": "%s claims a licence without a stated basis" % stage})
        for art in row.get("artifacts") or []:
            if len(str(art.get("sha256") or "")) != 64:
                findings.append({"level": "error",
                                 "text": "%s artifact without sha256" % stage})
    if total > CEILING_EUR:
        findings.append({"level": "error",
                         "text": "budget %.2f EUR exceeds ceiling %.2f" % (total, CEILING_EUR)})
    return {"total_cost_eur": round(total, 3), "stages": sorted(seen), "findings": findings}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-dir", required=True)
    parser.add_argument("--evidence")
    ns = parser.parse_args(argv)

    job = Path(ns.job_dir).resolve()
    if not job.is_dir():
        print("FINANCE_BLOCKED job_dir_missing")
        return 2
    rows = load_evidences(job)
    report = audit(rows)
    report.update({"schema": "ahos.finance-report.v1",
                   "job_dir": str(job),
                   "evidence_files": len(rows),
                   "ceiling_eur": CEILING_EUR,
                   "status": "PASSED" if not report["findings"] else "FAILED",
                   "generated_at": datetime.now(timezone.utc).isoformat()})
    if ns.evidence:
        Path(ns.evidence).parent.mkdir(parents=True, exist_ok=True)
        Path(ns.evidence).write_text(json.dumps(report, indent=2, ensure_ascii=False),
                                     encoding="utf-8")
    for finding in report["findings"]:
        print("  [%s] %s" % (finding["level"], finding["text"]))
    print("FINANCE_%s stages=%d total=%.2f EUR findings=%d"
          % (report["status"], len(report["stages"]), report["total_cost_eur"],
             len(report["findings"])))
    return 0 if report["status"] == "PASSED" else 2


if __name__ == "__main__":
    sys.exit(main())
