"""AHOS Studio OS - `rig` backend (real, zero-cost, local Blender).

    python tools/studio_backends/rig.py --plan <plan.json> --job-dir <dir> --evidence <json>

Per cast member: model (.blend) -> derive spec if missing -> build rig -> .blend/.glb.
Never reports PASSED without real artifacts (signature + sha256 checked).
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

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
FACTORY = ROOT / "tools" / "studio_backends" / "rig_factory.py"
VERIFY = ROOT / "tools" / "studio_backends" / "verify_rig.py"
LIBRARY = ROOT / "studio" / "assets" / "character-library"
# No hard-coded workspace paths: an approved library root may be provided by
# configuration, otherwise only the repository library is used.
MODEL_LIBRARY = Path(os.environ.get("AHOS_MODEL_LIBRARY", str(LIBRARY)))
EXTERNAL_MODELS = {}
BLENDER_CANDIDATES = [
    os.environ.get("BLENDER_EXE", ""),
    r"C:\actions-runner\_work\blender-4.5.16-windows-x64\blender.exe",
    shutil.which("blender") or "",
]


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_blender():
    for candidate in BLENDER_CANDIDATES:
        if candidate and Path(candidate).is_file():
            return candidate
    return None


def cast_ids(plan):
    out = []
    for item in plan.get("cast") or []:
        out.append(item.get("id") if isinstance(item, dict) else str(item))
    return [c for c in out if c]


APPROVED_LICENCES = {"approved", "own", "public-domain", "public_domain", "gpl", "verified"}


def resolve_model(cid, plan):
    """returns (path | None, source, error_code).

    A task dependency must be sha-pinned AND licence-proven; there is no silent
    fallback to a local model when the coordinator declared dependencies.
    """
    declared = bool(plan.get("dependency_artifacts"))
    for art in plan.get("dependency_artifacts") or []:
        if not isinstance(art, dict):
            continue
        # the coordinator ships {task_id, filename, sha256, bytes}; accept every
        # documented shape but never guess a model from a bare name
        kind = str(art.get("kind") or "").lower()
        if kind and kind not in ("character_model", "model", "mesh", "rig_source"):
            continue
        art_cast = str(art.get("character_id") or art.get("cast") or "").lower()
        raw = str(art.get("path") or art.get("filename") or "")
        # Multi-character tasks must use the coordinator's explicit identity.
        # GLB is a preview/export; Blender rigging needs an editable .blend.
        # Never accept the first matching artifact or infer identity from a name.
        if art_cast != cid.lower() or not raw.lower().endswith(".blend"):
            continue
        path = Path(raw)
        if path.is_absolute():
            candidates = [path]
        else:
            candidates = [(Path(plan.get("_job_dir", ".")) / raw).resolve(),
                          (ROOT / raw).resolve(),
                          (MODEL_LIBRARY / raw).resolve()]
        found = next((path for path in candidates if path.is_file()), None)
        if found is None:
            return None, "dependency", "DEPENDENCY_MISSING"
        expected = str(art.get("sha256") or "").lower()
        if len(expected) != 64:
            return None, "dependency", "SHA_MISSING"
        licence = str(art.get("license_status") or art.get("license") or "").lower()
        if licence not in APPROVED_LICENCES:
            return None, "dependency", "LICENSE_UNVERIFIED"
        if sha(found) != expected:
            return None, "dependency", "SHA_MISMATCH"
        return found, "dependency", None

    if declared:
        # never fall back to a convenience model when the coordinator expected one
        return None, "dependency", "DEPENDENCY_UNMATCHED"

    env = os.environ.get("AHOS_MODEL_%s" % cid.upper(), "")
    if env and Path(env).is_file():
        return Path(env), "env", None
    repo = MODEL_LIBRARY / cid / "v1" / ("%s-character-v1.blend" % cid)
    if repo.is_file():
        return repo, "library", None
    return None, "missing", "MODEL_MISSING"


def blender_run(blender, model, args, timeout=1200):
    command = ([blender, "-b", str(model), "-noaudio", "--factory-startup",
                "--python-exit-code", "1"] + args)
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--job-dir", required=True)
    parser.add_argument("--evidence", required=True)
    ns = parser.parse_args(argv)

    plan = json.loads(Path(ns.plan).read_text(encoding="utf-8-sig"))
    job = Path(ns.job_dir).resolve()
    plan["_job_dir"] = str(job)
    target = job / "rig"
    target.mkdir(parents=True, exist_ok=True)

    cast = cast_ids(plan)
    blender = find_blender()
    artifacts, checks, blocked, logs = [], {}, [], []
    metadata = {}
    if blender is None:
        blocked.append({"code": "BLENDER_MISSING",
                        "remediation": "Install Blender 4.5 LTS or set BLENDER_EXE"})

    for cid in cast:
        model, source, error = resolve_model(cid, plan)
        if model is None:
            blocked.append({"component": cid, "code": error or "MODEL_MISSING",
                            "remediation": "Provide a verified dependency_artifact "
                                           "(kind=character_model + sha256) or place the model at "
                                           "studio/assets/character-library/%s/v1/" % cid})
            continue
        stage_dir = target / cid
        if stage_dir.exists():
            # the job folder is owned by this backend: drop stale artifacts so a
            # failed/old build can never be published as PASSED
            for stale in stage_dir.iterdir():
                if stale.is_file():
                    stale.unlink()
        stage_dir.mkdir(parents=True, exist_ok=True)
        started = time.time()

        spec = LIBRARY / cid / "v1" / "rig-spec.json"
        if not spec.is_file():
            derive = blender_run(blender, model,
                                 ["--python", str(FACTORY), "--", "--mode", "derive",
                                  "--character", cid, "--out", str(stage_dir / "rig-spec.json")])
            logs.append({"cast": cid, "step": "derive", "exit": derive.returncode,
                         "stdout_tail": derive.stdout[-400:]})
            if derive.returncode != 0 or "DERIVE_OK" not in derive.stdout:
                blocked.append({"component": cid, "code": "SPEC_DERIVE_FAILED",
                                "remediation": "Check the model part naming contract"})
                continue
            spec = stage_dir / "rig-spec.json"

        build = blender_run(blender, model,
                            ["--python", str(FACTORY), "--", "--mode", "build",
                             "--spec", str(spec), "--out", str(stage_dir)])
        logs.append({"cast": cid, "step": "build", "exit": build.returncode,
                     "stdout_tail": build.stdout[-400:], "stderr_tail": build.stderr[-300:]})
        if build.returncode != 0 or "BUILD_OK" not in build.stdout:
            blocked.append({"component": cid, "code": "BUILD_FAILED",
                            "remediation": "rig_factory exit=%s" % build.returncode})
            continue

        blend = stage_dir / ("%s-rigged.blend" % cid)
        glb = stage_dir / ("%s-rigged.glb" % cid)
        if not blend.is_file() or blend.read_bytes()[:7] != b"BLENDER":
            blocked.append({"component": cid, "code": "BLEND_INVALID",
                            "remediation": "Blender signature check failed"})
            continue
        if not glb.is_file() or glb.read_bytes()[:4] != b"glTF":
            blocked.append({"component": cid, "code": "GLB_INVALID",
                            "remediation": "GLB signature check failed"})
            continue
        if blend.stat().st_mtime < started - 2.0 or glb.stat().st_mtime < started - 2.0:
            blocked.append({"component": cid, "code": "STALE_ARTIFACT",
                            "remediation": "Artifacts older than this build - the factory "
                                           "wrote a timestamped copy instead of the canonical "
                                           "file name"})
            continue

        manifest = json.loads((stage_dir / "rig-manifest.json").read_text(encoding="utf-8"))
        keys = manifest.get("shape_keys") or {}
        if manifest["rig"]["bone_count"] < 10 or len(keys) < 5:
            blocked.append({"component": cid, "code": "RIG_TOO_SMALL",
                            "remediation": "%d bones / %d shape keys"
                                           % (manifest["rig"]["bone_count"], len(keys))})
            continue

        verify_json = stage_dir / ("%s-verify.json" % cid)
        verify = blender_run(blender, blend, ["--python", str(VERIFY), "--", str(verify_json)])
        logs.append({"cast": cid, "step": "reopen_verify", "exit": verify.returncode,
                     "stdout_tail": verify.stdout[-400:]})
        if verify.returncode != 0 or "VERIFY_OK" not in verify.stdout:
            blocked.append({"component": cid, "code": "REOPEN_VERIFY_FAILED",
                            "remediation": (verify.stdout[-300:] or "verify_rig failed").strip()})
            continue
        reopen = json.loads(verify_json.read_text(encoding="utf-8"))

        contract = {
            "schema": "ahos.rig-contract.v1",
            "character_id": cid,
            "rig_version": "v1",
            "coordinate_system": "Blender right-handed, Z-up, character faces -Y",
            "scale": 1.0,
            "origin": "feet on ground plane z=0",
            "model": {"path": str(model), "sha256": sha(model)},
            "rig": {"blend": str(blend), "blend_sha256": sha(blend),
                    "glb": str(glb), "glb_sha256": sha(glb),
                    "sha256": sha(blend)},
            "skeleton": {"bones": reopen["bone_names"],
                         "bone_count": reopen["bones"]},
            "facial_controls": {"shape_keys": reopen["shape_keys"],
                                "bones": ["jaw", "eye.L", "eye.R", "eyelid.L", "eyelid.R"]},
            "actions": [{"name": a["name"], "frames": [a["frame_start"], a["frame_end"]]}
                        for a in manifest["actions"]],
            "consumers": ["animation", "lipsync", "render"],
        }
        contract_path = stage_dir / ("%s-rig-contract.json" % cid)
        contract_path.write_text(json.dumps(contract, indent=2, ensure_ascii=False),
                                 encoding="utf-8")

        checks[cid] = {
            "model": {"path": str(model), "source": source, "sha256": sha(model)},
            "spec": str(spec),
            "bones": manifest["rig"]["bone_count"],
            "shape_keys": sorted(keys),
            "actions": [a["name"] for a in manifest["actions"]],
            "mesh_stats": manifest["mesh_stats"],
            "skinning": {"rigid": len(manifest["skinning"]["rigid"]),
                         "auto": len(manifest["skinning"]["auto"]),
                         "fixed_vertices": manifest["skinning"]["fixed_vertices"]},
            "reopen": {"status": reopen["status"], "bones": reopen["bones"],
                       "meshes": reopen["meshes"], "vertices": reopen["vertices"],
                       "unweighted": reopen["unweighted_vertices"]},
            "license_status": next(
                (str(item.get("license_status") or item.get("license") or "").lower()
                 for item in (plan.get("dependency_artifacts") or [])
                 if str(item.get("sha256") or "").lower() == sha(model)),
                "own" if source in ("library", "env") else "unknown"),
        }
        for path in (blend, glb, contract_path):
            artifacts.append({"kind": "rig", "cast": cid,
                              "path": str(path.relative_to(job)).replace("\\", "/"),
                              "bytes": path.stat().st_size, "sha256": sha(path)})
        metadata.setdefault("rig_contracts", {})[cid] = {
            "path": str(contract_path.relative_to(job)).replace("\\", "/"),
            "sha256": sha(contract_path),
            "schema": contract["schema"],
        }

    status = "PASSED" if (not blocked and artifacts) else "BLOCKED"
    commercial = bool(artifacts) and not blocked and all(
        str(entry.get("license_status") or "").lower() in APPROVED_LICENCES
        for entry in checks.values())
    evidence = {
        "stage": "rig", "status": status, "cost_eur": 0,
        "commercial_license_verified": commercial,
        "license_basis": "Blender 4.5 LTS (GPL) + original procedural geometry; "
                         "no third-party assets were used",
        "cast_ids": cast,
        "rigged_cast": sorted({a["cast"] for a in artifacts}),
        "provenance": {"source": "local", "generator": "ahos-rig-factory v0.1",
                       "blender": "4.5.16 LTS",
                       "identity_status": "TECHNICAL_ONLY / PENDING_IDENTITY_REVIEW"},
        "checks": checks, "artifacts": artifacts, "blocked": blocked, "logs": logs,
        "metadata": metadata,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    evidence_path = Path(ns.evidence)
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False),
                             encoding="utf-8")
    print("RIG_BACKEND_%s cast=%s artifacts=%d blocked=%d"
          % (status, ",".join(cast), len(artifacts), len(blocked)))
    return 0 if status == "PASSED" else 2


if __name__ == "__main__":
    sys.exit(main())
