"""AHOS Studio OS - `scene` backend v0.1 (environment, lights, shot cameras).

    python tools/studio_backends/scene.py --plan plan.json --job-dir DIR --evidence EV.json

Consumes the approved animation artefact (kind=animation, .blend), runs the scene
factory in Blender and publishes <character>-scene.blend/.glb plus cameras.
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
FACTORY = ROOT / "tools" / "studio_backends" / "scene_factory.py"
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


def pick(plan, kinds, suffix):
    for art in plan.get("dependency_artifacts") or []:
        if not isinstance(art, dict):
            continue
        kind = str(art.get("kind") or "").lower()
        raw = str(art.get("path") or art.get("filename") or "")
        if kind and kind not in kinds:
            continue
        if not raw.lower().endswith(suffix):
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
    return None, "ANIMATION_DEPENDENCY_REQUIRED"


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--job-dir", required=True)
    parser.add_argument("--evidence", required=True)
    ns = parser.parse_args(argv)

    job = Path(ns.job_dir).resolve()
    plan = json.loads(Path(ns.plan).read_text(encoding="utf-8-sig"))
    plan["_job_dir"] = str(job)
    out = job / "scene"
    if out.exists():
        for stale in out.iterdir():
            if stale.is_file():
                stale.unlink()
    out.mkdir(parents=True, exist_ok=True)

    blender = find_blender()
    coach = growth.guidance("scene")
    artifacts, checks, blocked = [], {}, []
    if blender is None:
        blocked.append({"code": "BLENDER_MISSING", "remediation": "install Blender 4.5"})

    source, error = pick(plan, {"animation"}, ".blend")
    if source is None:
        blocked.append({"code": error,
                        "remediation": "approved animation .blend required"})
    elif blender:
        started = time.time()
        run = subprocess.run([blender, "-b", str(source), "-noaudio", "--factory-startup",
                              "--python-exit-code", "1", "--python", str(FACTORY),
                              "--", "--out", str(out)],
                             capture_output=True, text=True, timeout=1200)
        if run.returncode != 0 or "SCENE_OK" not in run.stdout:
            blocked.append({"code": "SCENE_BUILD_FAILED",
                            "remediation": (run.stdout + run.stderr)[-300:].strip()})
        else:
            stem = source.stem
            blend = out / (stem + "-scene.blend")
            glb = out / (stem + "-scene.glb")
            good = (blend.is_file() and blend.read_bytes()[:7] == b"BLENDER"
                    and glb.is_file() and glb.read_bytes()[:4] == b"glTF"
                    and blend.stat().st_mtime >= started - 2.0)
            if not good:
                blocked.append({"code": "SCENE_ARTIFACT_INVALID",
                                "remediation": "signature/freshness check failed"})
            else:
                manifest = json.loads((out / "scene-manifest.json").read_text(encoding="utf-8"))
                checks[stem] = {"source": str(source), "source_sha256": sha(source),
                                "cameras": sorted(manifest["cameras"]),
                                "lights": manifest["lights"], "props": manifest["props"]}
                for path in (blend, glb):
                    artifacts.append({"kind": "scene", "cast": ",".join(cast_ids(plan)),
                                      "path": str(path.relative_to(job)).replace("\\", "/"),
                                      "bytes": path.stat().st_size, "sha256": sha(path)})

    status = "PASSED" if (artifacts and not blocked) else "BLOCKED"
    evidence = {"stage": "scene", "status": status, "cost_eur": 0,
                "commercial_license_verified": status == "PASSED",
                "license_basis": "Blender 4.5 (GPL) + original procedural set",
                "cast_ids": cast_ids(plan), "checks": checks, "artifacts": artifacts,
                "blocked": blocked, "growth": coach, "memory": memory.digest("scene"),
                "generated_at": datetime.now(timezone.utc).isoformat()}
    memory.remember("scene", {"status": status, "cast": cast_ids(plan),
                              "artifacts": len(artifacts),
                              "blocked_codes": [b.get("code") for b in blocked]})
    evidence["memory_after"] = memory.digest("scene")
    Path(ns.evidence).parent.mkdir(parents=True, exist_ok=True)
    Path(ns.evidence).write_text(json.dumps(evidence, indent=2, ensure_ascii=False),
                                 encoding="utf-8")
    print("SCENE_BACKEND_%s artifacts=%d blocked=%d"
          % (status, len(artifacts), len(blocked)))
    return 0 if status == "PASSED" else 2


if __name__ == "__main__":
    sys.exit(main())

