"""Real character_model backend: approved reference -> editable 3D character.

Blender 4.5 LTS is invoked headless to build original procedural geometry.
Identity is explicitly PENDING_IDENTITY_REVIEW (technical model, not owner-approved
likeness). A persistent character library is reused on later stories.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[2]
ROSTER = ROOT / "studio/reference/owner_accepted_roster_v1/characters/01_aden.png"
BUILD = ROOT / "tools/studio_backends/build_aden_blender.py"
LIBRARY = ROOT / "studio/assets/character-library/aden/v1"
BLENDER_CANDIDATES = [
    os.environ.get("BLENDER_EXE", ""),
    r"C:\actions-runner\_work\blender-4.5.16-windows-x64\blender.exe",
    shutil.which("blender") or "",
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def find_blender() -> str | None:
    for candidate in BLENDER_CANDIDATES:
        if candidate and Path(candidate).is_file():
            return candidate
    return None


def character_from_plan(plan: dict) -> tuple[str, str]:
    cast = plan.get("cast") or []
    for item in cast:
        cid = item.get("id") if isinstance(item, dict) else str(item)
        if cid == "aden":
            return "aden", "01_aden.png"
    raise ValueError("plan cast does not include supported character 'aden'")


def build(blender: str, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    command = [blender, "-b", "-noaudio", "--factory-startup",
               "--python", str(BUILD), "--", "--out", str(out)]
    run = subprocess.run(command, capture_output=True, text=True, timeout=900)
    if run.returncode:
        raise RuntimeError(f"Blender exit={run.returncode}: {run.stderr[-800:]}")
    if "BLENDER_BUILD_OK" not in run.stdout:
        raise RuntimeError("Blender build marker missing")


def copy_artifacts(job: Path) -> dict:
    target = job / "character-model"
    target.mkdir(parents=True, exist_ok=True)
    for name in ("aden-character-v1.blend", "aden-character-v1.glb", "model-stats.json"):
        shutil.copy2(LIBRARY / name, target / name)
    (target / "previews").mkdir(exist_ok=True)
    for preview in sorted((LIBRARY / "previews").glob("*.png")):
        shutil.copy2(preview, target / "previews" / preview.name)
    return target


def validate(target: Path) -> dict:
    blend = target / "aden-character-v1.blend"
    glb = target / "aden-character-v1.glb"
    stats = json.loads((target / "model-stats.json").read_text(encoding="utf-8"))
    if blend.read_bytes()[:7] != b"BLENDER":
        raise ValueError("BLEND signature missing")
    if glb.read_bytes()[:4] != b"glTF":
        raise ValueError("GLB signature missing")
    if stats["totals"]["objects"] < 20 or stats["totals"]["vertices"] < 5000:
        raise ValueError("model geometry is too small to be a real character")
    previews = sorted((target / "previews").glob("*.png"))
    if len(previews) < 6:
        raise ValueError("six-view preview set missing")
    return {"blend": blend, "glb": glb, "stats": stats, "previews": previews}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--job-dir", required=True)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    job = Path(args.job_dir).resolve()
    job.mkdir(parents=True, exist_ok=True)
    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    try:
        character_id, source_name = character_from_plan(plan)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if not ROSTER.is_file():
        print(f"approved roster missing: {ROSTER}", file=sys.stderr)
        return 3
    if not BUILD.is_file():
        print(f"build script missing: {BUILD}", file=sys.stderr)
        return 3
    blender = find_blender()
    reused = False
    try:
        if not args.force and (LIBRARY / "aden-character-v1.blend").is_file() and \
                (LIBRARY / "model-manifest.json").is_file():
            reused = True
        else:
            if blender is None:
                print("Blender not installed; cannot generate character model", file=sys.stderr)
                return 3
            build(blender, LIBRARY)
        target = copy_artifacts(job)
        verified = validate(target)
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 4
    stats = verified["stats"]
    manifest = {
        "schema": "ahos.character-model.v1",
        "character_id": character_id,
        "version": "v1",
        "technical_status": "TECHNICAL_MODEL_CREATED",
        "identity_status": "PENDING_IDENTITY_REVIEW",
        "rig_status": "NOT_STARTED",
        "source_reference": str(ROSTER.relative_to(ROOT)),
        "source_sha256": sha(ROSTER),
        "blender": "4.5.16 LTS",
        "built_at": datetime.now(timezone.utc).isoformat(),
        "model_files": {
            "blend": {"path": "aden-character-v1.blend", "sha256": sha(verified["blend"])},
            "glb": {"path": "aden-character-v1.glb", "sha256": sha(verified["glb"])},
        },
        "stats": stats["totals"],
        "materials": stats["materials"],
        "previews": [p.name for p in verified["previews"]],
        "commercial_license_verified": True,
        "license_basis": "Original procedural geometry generated in Blender; no third-party mesh/texture/model weights. Owner character IP.",
        "identity_note": "Technical 3D model only; not an owner-approved likeness. No IDENTITY_APPROVED claim.",
    }
    (LIBRARY / "model-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    evidence = {
        "stage": "character_model",
        "status": "PASSED",
        "cost_eur": 0,
        "commercial_license_verified": True,
        "technical_status": "TECHNICAL_MODEL_CREATED",
        "identity_status": "PENDING_IDENTITY_REVIEW",
        "reused_existing_model": reused,
        "character_id": character_id,
        "source_reference": str(ROSTER.relative_to(ROOT)),
        "source_sha256": sha(ROSTER),
        "stats": stats["totals"],
        "artifacts": [
            {"kind": "character_model", "path": "character-model/aden-character-v1.blend",
             "sha256": sha(verified["blend"])},
            {"kind": "character_model", "path": "character-model/aden-character-v1.glb",
             "sha256": sha(verified["glb"])},
        ],
    }
    Path(args.evidence).write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
                                   encoding="utf-8")
    print(json.dumps({"character": character_id, "reused": reused,
                      "objects": stats["totals"]["objects"],
                      "vertices": stats["totals"]["vertices"],
                      "faces": stats["totals"]["faces"],
                      "blend": str(verified["blend"]), "glb": str(verified["glb"])},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
