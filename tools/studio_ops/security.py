"""AHOS Studio Ops - `security` worker: rights & licence gate (read-only).

    python tools/studio_ops/security.py [--job-dir DIR] [--evidence OUT.json]

Checks every asset/voice manifest for a recorded licence status and refuses any
stage evidence that claims a commercial licence without a stated basis. It never
grants rights and never edits files.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APPROVED = {"approved", "own", "public-domain", "public_domain", "gpl", "verified"}
REVIEW = {"review_required", "pending", "pending_reference", "unverified"}


def iter_json(paths):
    for root in paths:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.json")):
            if any(part in ("jobs", "__pycache__") for part in path.parts):
                continue
            try:
                yield path, json.loads(path.read_text(encoding="utf-8-sig"))
            except ValueError:
                continue


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-dir")
    parser.add_argument("--evidence")
    ns = parser.parse_args(argv)

    roots = [ROOT / "studio" / "assets", ROOT / "studio" / "agents", ROOT / "studio" / "audio"]
    if ns.job_dir:
        roots.append(Path(ns.job_dir).resolve())

    findings, assets, licences = [], 0, {}
    for path, payload in iter_json(roots):
        rel = str(path.relative_to(ROOT)).replace("\\", "/") if path.is_absolute() else str(path)
        if isinstance(payload, dict) and "profiles" in payload:
            for cid, langs in (payload.get("profiles") or {}).items():
                for lang, profile in (langs or {}).items():
                    status = str((profile or {}).get("license_status") or "").lower()
                    licences["%s/%s" % (cid, lang)] = status
                    if not status:
                        findings.append({"level": "error",
                                         "text": "voice profile %s/%s has no licence status"
                                                 % (cid, lang)})
                    elif status in REVIEW:
                        findings.append({"level": "warn",
                                         "text": "voice %s/%s licence=%s" % (cid, lang, status)})
        if isinstance(payload, dict) and "artifacts" in payload:
            assets += len(payload.get("artifacts") or [])
            if payload.get("commercial_license_verified") is True:
                if len(str(payload.get("license_basis") or "")) < 8:
                    findings.append({"level": "error",
                                     "text": "%s claims a licence without basis" % rel})
        if isinstance(payload, dict) and payload.get("identity_status") == "TECHNICAL_ONLY":
            licences.setdefault(rel, "technical_only")

    errors = [f for f in findings if f["level"] == "error"]
    report = {
        "schema": "ahos.rights-report.v1",
        "checked_profiles": len(licences),
        "checked_artifacts": assets,
        "approved_licences": sorted(k for k, v in licences.items() if v in APPROVED),
        "pending_licences": sorted(k for k, v in licences.items() if v in REVIEW),
        "status": "PASSED" if not errors else "FAILED",
        "findings": findings,
        "note": "review_required is not a failure: it marks assets whose commercial "
                "use still needs the owner's decision",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    if ns.evidence:
        Path(ns.evidence).parent.mkdir(parents=True, exist_ok=True)
        Path(ns.evidence).write_text(json.dumps(report, indent=2, ensure_ascii=False),
                                     encoding="utf-8")
    for finding in findings:
        print("  [%s] %s" % (finding["level"], finding["text"]))
    print("SECURITY_%s profiles=%d artifacts=%d approved=%d pending=%d errors=%d"
          % (report["status"], report["checked_profiles"], report["checked_artifacts"],
             len(report["approved_licences"]), len(report["pending_licences"]), len(errors)))
    return 0 if report["status"] == "PASSED" else 2


if __name__ == "__main__":
    sys.exit(main())
