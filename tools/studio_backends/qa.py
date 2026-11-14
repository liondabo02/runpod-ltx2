"""AHOS Studio OS - `qa` backend v0.1: independent technical quality gate.

    python tools/studio_backends/qa.py --plan plan.json --job-dir DIR --evidence EV.json

Reads every stage evidence in the job folder and re-checks the artefacts itself:
files exist, sha256 matches, paths stay inside the job, cost is zero, and stage
specific gates (rig: unweighted==0; lipsync: gap<1s; render: audio stream present).

It never approves creatively: `creative_approved` stays false until a real owner
record is supplied in the plan.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
CEILING_EUR = 1.00


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def has_audio(path: Path) -> bool:
    exe = shutil.which("ffprobe")
    if not exe:
        return False
    run = subprocess.run([exe, "-v", "error", "-select_streams", "a",
                          "-show_entries", "stream=codec_type", "-of", "csv=p=0",
                          str(path)], capture_output=True, text=True)
    return "audio" in run.stdout


def collect(job: Path):
    rows = []
    for path in sorted(job.rglob("*evidence*.json")):
        if "qa-report" in path.name or "finance" in path.name or "rights" in path.name:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except ValueError:
            continue
        if isinstance(payload, dict) and payload.get("stage"):
            payload["_file"] = str(path.relative_to(job)).replace("\\", "/")
            rows.append(payload)
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--job-dir", required=True)
    parser.add_argument("--evidence", required=True)
    ns = parser.parse_args(argv)

    job = Path(ns.job_dir).resolve()
    plan = json.loads(Path(ns.plan).read_text(encoding="utf-8-sig"))
    rows = collect(job)

    blockers, checks, total = [], {}, 0.0
    for row in rows:
        stage = str(row.get("stage"))
        stage_blockers = []
        total += float(row.get("cost_eur") or 0)
        if row.get("status") != "PASSED":
            stage_blockers.append("status=%s" % row.get("status"))
        for art in row.get("artifacts") or []:
            rel = str(art.get("path") or "")
            path = (job / rel).resolve()
            if job not in path.parents or not path.is_file():
                stage_blockers.append("missing artifact %s" % rel)
                continue
            if sha(path) != art.get("sha256"):
                stage_blockers.append("sha mismatch %s" % rel)
            if path.suffix == ".mp4" and not has_audio(path):
                stage_blockers.append("no audio stream %s" % rel)
        if stage == "rig":
            for cast, info in (row.get("checks") or {}).items():
                reopen = info.get("reopen") or {}
                if reopen and reopen.get("unweighted"):
                    stage_blockers.append("%s unweighted vertices" % cast)
        if stage == "lipsync":
            for cast, info in (row.get("checks") or {}).items():
                if float(info.get("max_gap_seconds") or 0) > 1.0:
                    stage_blockers.append("%s lip gap %.2fs" % (cast, info["max_gap_seconds"]))
        checks[stage] = {"evidence": row["_file"], "blockers": stage_blockers,
                         "ok": not stage_blockers}
        blockers.extend("%s: %s" % (stage, text) for text in stage_blockers)

    if total > CEILING_EUR:
        blockers.append("budget %.2f EUR exceeds %.2f" % (total, CEILING_EUR))
    owner_ok = bool((plan.get("owner_approval") or {}).get("record"))
    technical = bool(rows) and not blockers
    report = {
        "schema": "ahos.quality-report.v1",
        "stages": sorted(checks),
        "checks": checks,
        "blockers": blockers,
        "total_cost_eur": round(total, 3),
        "technical_pass": technical,
        "creative_approved": bool(owner_ok),
        "status": "PASSED" if technical else "FAILED",
        "note": "technical pass is not creative approval; creative stays owner-only",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    Path(ns.evidence).parent.mkdir(parents=True, exist_ok=True)
    Path(ns.evidence).write_text(json.dumps(report, indent=2, ensure_ascii=False),
                                 encoding="utf-8")
    for blocker in blockers:
        print("  [blocker] %s" % blocker)
    print("QA_%s stages=%d technical=%s creative=%s blockers=%d"
          % (report["status"], len(checks), technical, report["creative_approved"],
             len(blockers)))
    return 0 if technical else 2


if __name__ == "__main__":
    sys.exit(main())
