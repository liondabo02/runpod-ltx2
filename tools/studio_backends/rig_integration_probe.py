"""Integration probe: does Studio OS accept the rig worker's evidence?

Uses the studio's own validator (studio_media_worker_client.read_evidence) and
checks that the emitted rig-contract is consumable by the Animation stage.

    python tools/studio_backends/rig_integration_probe.py <job_dir>
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from studio_media_worker_client import WorkerError, read_evidence  # noqa: E402

job = Path(sys.argv[1]).resolve()
evidence_path = job / "rig-evidence.json"
data = json.loads(evidence_path.read_text(encoding="utf-8")) if evidence_path.is_file() else {}

accepted, error, uploaded = False, "", []
try:
    uploaded = [name for name, _ in read_evidence(evidence_path, "rig", job)]
    accepted = True
except WorkerError as exc:
    error = str(exc)

problems = []
contracts = data.get("metadata", {}).get("rig_contracts", {})
checks = data.get("checks", {})
for cid, meta in contracts.items():
    contract = json.loads((job / meta["path"]).read_text(encoding="utf-8"))
    if contract["skeleton"]["bone_count"] != checks[cid]["reopen"]["bones"]:
        problems.append("%s: bone count mismatch" % cid)
    if [a["name"] for a in contract["actions"]] != checks[cid]["actions"]:
        problems.append("%s: action list mismatch" % cid)
    if sorted(contract["facial_controls"]["shape_keys"]) != sorted(checks[cid]["shape_keys"]):
        problems.append("%s: shape key mismatch" % cid)
    if len(contract["skeleton"]["bones"]) < 10:
        problems.append("%s: skeleton too small" % cid)

print("READ_EVIDENCE: %s%s" % ("OK" if accepted else "REJECTED", (" (%s)" % error) if error else ""))
print("UPLOAD_FILES  : %s" % (", ".join(sorted(uploaded)) or "-"))
print("CONTRACTS     : %s" % (", ".join(sorted(contracts)) or "-"))
print("CONSUMER      : %s" % ("OK" if not problems else "FAILED " + "; ".join(problems)))
sys.exit(0 if accepted and not problems else 2)
