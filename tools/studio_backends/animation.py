"""AHOS Studio OS - `animation` backend (beat-driven acting, zero cost).

    python tools/studio_backends/animation.py --plan <plan.json> --job-dir <dir> --evidence <json>

Consumes the rig stage output (rigged .blend + rig-contract.json) delivered as
dependency artifacts, builds a beat-driven action and publishes .blend/.glb plus
the animation manifest. No character-specific code.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
FACTORY = ROOT / "tools" / "studio_backends" / "animation_factory.py"
APPROVED = {"approved", "own", "public-domain", "public_domain", "gpl", "verified"}
BLENDER = [os.environ.get("BLENDER_EXE", ""),
           r"C:\actions-runner\_work\blender-4.5.16-windows-x64\blender.exe",
           shutil.which("blender") or ""]


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_blender():
    for candidate in BLENDER:
        if candidate and Path(candidate).is_file():
            return candidate
    return None


def cast_ids(plan):
    out = []
    for item in plan.get("cast") or []:
        out.append(item.get("id") if isinstance(item, dict) else str(item))
    return [c for c in out if c]


def resolve_rig(cid, plan):
    for art in plan.get("dependency_artifacts") or []:
        if not isinstance(art, dict):
            continue
        kind = str(art.get("kind") or "").lower()
        raw = str(art.get("path") or art.get("filename") or "")
        art_cast = str(art.get("cast") or art.get("character_id") or "").lower()
        if kind and kind != "rig":
            continue
        if art_cast and art_cast != cid.lower():
            continue
        if not raw.lower().endswith(".blend"):
            continue
        path = Path(raw)
        candidates = [path] if path.is_absolute() else [
            (Path(plan.get("_job_dir", ".")) / raw).resolve(), (ROOT / raw).resolve()]
        found = next((p for p in candidates if p.is_file()), None)
        if found is None:
            return None, "DEPENDENCY_MISSING"
        expected = str(art.get("sha256") or "").lower()
        if len(expected) != 64:
            return None, "SHA_MISSING"
        if sha(found) != expected:
            return None, "SHA_MISMATCH"
        if str(art.get("license_status") or "").lower() not in APPROVED:
            return None, "LICENSE_UNVERIFIED"
        return found, None
    return None, "RIG_DEPENDENCY_REQUIRED"


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--job-dir", required=True)
    parser.add_argument("--evidence", required=True)
    ns = parser.parse_args(argv)

    job = Path(ns.job_dir).resolve()
    job.mkdir(parents=True, exist_ok=True)
    plan = json.loads(Path(ns.plan).read_text(encoding="utf-8-sig"))
    plan["_job_dir"] = str(job)

    out = job / "animation"
    if out.exists():
        for stale in out.iterdir():
            if stale.is_file():
                stale.unlink()
    out.mkdir(parents=True, exist_ok=True)

    blender = find_blender()
    cast = cast_ids(plan)
    artifacts, checks, blocked, logs, metadata = [], {}, [], [], {}
    if blender is None:
        blocked.append({"code": "BLENDER_MISSING", "remediation": "Install Blender 4.5"})

    for cid in cast:
        rig, error = resolve_rig(cid, plan)
        if rig is None:
            blocked.append({"component": cid, "code": error,
                            "remediation": "Provide the QA-approved rig artifact "
                                           "(kind=rig, sha256, license_status)"})
            continue
        contract = next(iter(rig.parent.glob("*-rig-contract.json")), None)
        if contract is None:
            contract = next(iter(job.glob("**/*-rig-contract.json")), None)
        if contract is None:
            blocked.append({"component": cid, "code": "CONTRACT_MISSING",
                            "remediation": "Rig stage must ship the rig contract"})
            continue

        plan_path = out / ("%s-animation-plan.json" % cid)
        plan_path.write_text(json.dumps(dict(plan, character_id=cid,
                                             rig_contract_sha256=sha(contract)),
                                        ensure_ascii=False, indent=2), encoding="utf-8")
        started = time.time()
        run = subprocess.run(
            [blender, "-b", str(rig), "-noaudio", "--factory-startup",
             "--python-exit-code", "1", "--python", str(FACTORY), "--",
             "--plan", str(plan_path), "--out", str(out), "--contract", str(contract)],
            capture_output=True, text=True, timeout=1800)
        logs.append({"cast": cid, "step": "animate", "exit": run.returncode,
                     "stdout_tail": run.stdout[-500:]})
        if run.returncode != 0 or "ANIMATION_OK" not in run.stdout:
            blocked.append({"component": cid, "code": "ANIMATION_FAILED",
                            "remediation": (run.stderr[-400:] or "factory failed").strip()})
            continue

        blend = out / ("%s-animated.blend" % cid)
        glb = out / ("%s-animated.glb" % cid)
        manifest = json.loads((out / "animation-manifest.json").read_text(encoding="utf-8"))
        if not blend.is_file() or blend.read_bytes()[:7] != b"BLENDER":
            blocked.append({"component": cid, "code": "BLEND_INVALID",
                            "remediation": "signature check failed"})
            continue
        if not glb.is_file() or glb.read_bytes()[:4] != b"glTF":
            blocked.append({"component": cid, "code": "GLB_INVALID",
                            "remediation": "signature check failed"})
            continue
        if min(blend.stat().st_mtime, glb.stat().st_mtime) < started - 2.0:
            blocked.append({"component": cid, "code": "STALE_ARTIFACT",
                            "remediation": "artifacts predate this run"})
            continue

        checks[cid] = {"rig": str(rig), "rig_sha256": sha(rig),
                       "contract": str(contract), "contract_sha256": sha(contract),
                       "action": manifest["action"], "frames": manifest["frame_range"],
                       "beats": [b["beat"] for b in manifest["beats"]]}
        for path in (blend, glb):
            artifacts.append({"kind": "animation", "cast": cid,
                              "path": str(path.relative_to(job)).replace("\\", "/"),
                              "bytes": path.stat().st_size, "sha256": sha(path)})
        metadata.setdefault("animation_manifests", {})[cid] = {
            "path": str((out / "animation-manifest.json").relative_to(job)).replace("\\", "/"),
            "sha256": sha(out / "animation-manifest.json")}

    status = "PASSED" if (artifacts and not blocked) else "BLOCKED"
    evidence = {
        "stage": "animation", "status": status, "cost_eur": 0,
        "commercial_license_verified": status == "PASSED",
        "license_basis": "Blender 4.5 LTS (GPL); rig from the approved local library",
        "cast_ids": cast, "animated_cast": sorted({a["cast"] for a in artifacts}),
        "provenance": {"source": "local", "generator": "ahos-animation-factory v0.1",
                       "identity_status": "TECHNICAL_ONLY / PENDING_IDENTITY_REVIEW"},
        "checks": checks, "artifacts": artifacts, "blocked": blocked,
        "logs": logs, "metadata": metadata,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    Path(ns.evidence).parent.mkdir(parents=True, exist_ok=True)
    Path(ns.evidence).write_text(json.dumps(evidence, indent=2, ensure_ascii=False),
                                 encoding="utf-8")
    print("ANIMATION_BACKEND_%s cast=%s artifacts=%d blocked=%d"
          % (status, ",".join(cast), len(artifacts), len(blocked)))
    return 0 if status == "PASSED" else 2


if __name__ == "__main__":
    sys.exit(main())

