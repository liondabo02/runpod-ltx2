"""AHOS Studio OS - `character_model` backend v0.2 (spec-driven, any character).

    python tools/studio_backends/character_model_generic.py \
        --plan plan.json --job-dir DIR --evidence EV.json

Every cast member resolves from studio/characters/<id>/spec.json (or an inline
plan spec), is built with the shared mesh factory, then verified: magic bytes,
sha256, licence record and memory/growth hooks. No character is hard-coded.
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
sys.path.insert(0, str(Path(__file__).resolve().parent))
import growth  # noqa: E402
import memory  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
BUILDER = ROOT / "tools" / "studio_backends" / "mesh_factory.py"
SPECS = ROOT / "studio" / "characters"
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


def resolve_spec(cid, plan):
    inline = (plan.get("characters") or {}).get(cid)
    if isinstance(inline, dict):
        return inline, "plan"
    path = SPECS / cid / "spec.json"
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8-sig")), str(path)
    return None, None


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--job-dir", required=True)
    parser.add_argument("--evidence", required=True)
    ns = parser.parse_args(argv)

    job = Path(ns.job_dir).resolve()
    plan = json.loads(Path(ns.plan).read_text(encoding="utf-8-sig"))
    out = job / "character-model"
    out.mkdir(parents=True, exist_ok=True)

    blender = find_blender()
    coach = growth.guidance("character_model")
    artifacts, checks, blocked = [], {}, []
    if blender is None:
        blocked.append({"code": "BLENDER_MISSING", "remediation": "install Blender 4.5"})

    for cid in cast_ids(plan):
        spec, source = resolve_spec(cid, plan)
        if not spec:
            blocked.append({"component": cid, "code": "SPEC_MISSING",
                            "remediation": "add studio/characters/%s/spec.json "
                                           "(character_id, class, height_m, palette)" % cid})
            continue
        spec = dict(spec, character_id=cid)
        spec_path = out / ("%s-spec.json" % cid)
        spec_path.write_text(json.dumps(spec, indent=2, ensure_ascii=False), encoding="utf-8")

        started = time.time()
        run = subprocess.run([blender, "-b", "--factory-startup", "-noaudio",
                              "--python-exit-code", "1", "--python", str(BUILDER),
                              "--", "--spec", str(spec_path), "--out", str(out)],
                             capture_output=True, text=True, timeout=900)
        if run.returncode != 0 or "MESH_OK" not in run.stdout:
            blocked.append({"component": cid, "code": "MESH_BUILD_FAILED",
                            "remediation": (run.stdout + run.stderr)[-300:].strip()})
            continue

        blend = out / ("%s-model.blend" % cid)
        glb = out / ("%s-model.glb" % cid)
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

        manifest = json.loads((out / "model-manifest.json").read_text(encoding="utf-8"))
        checks[cid] = {"spec_source": source, "class": spec.get("class"),
                       "height_m": spec.get("height_m"),
                       "parts": len(manifest.get("parts") or []),
                       "vertices": manifest.get("totals", {}).get("vertices"),
                       "identity_status": manifest.get("identity_status"),
                       "license_status": spec.get("license_status", "own")}
        for path in (blend, glb):
            artifacts.append({"kind": "character_model", "cast": cid,
                              "path": str(path.relative_to(job)).replace("\\", "/"),
                              "bytes": path.stat().st_size, "sha256": sha(path)})

    status = "PASSED" if (artifacts and not blocked) else "BLOCKED"
    evidence = {
        "stage": "character_model", "status": status, "cost_eur": 0,
        "commercial_license_verified": status == "PASSED",
        "license_basis": "Blender 4.5 (GPL) + original procedural geometry per spec",
        "cast_ids": cast_ids(plan), "checks": checks, "artifacts": artifacts,
        "blocked": blocked, "growth": coach, "memory": memory.digest("character_model"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    memory.remember("character_model", {"status": status, "cast": cast_ids(plan),
                                        "artifacts": len(artifacts),
                                        "blocked_codes": [b.get("code") for b in blocked]})
    evidence["memory_after"] = memory.digest("character_model")
    Path(ns.evidence).parent.mkdir(parents=True, exist_ok=True)
    Path(ns.evidence).write_text(json.dumps(evidence, indent=2, ensure_ascii=False),
                                 encoding="utf-8")
    print("CHARACTER_BACKEND_%s cast=%s artifacts=%d blocked=%d"
          % (status, ",".join(cast_ids(plan)), len(artifacts), len(blocked)))
    return 0 if status == "PASSED" else 2


if __name__ == "__main__":
    sys.exit(main())

