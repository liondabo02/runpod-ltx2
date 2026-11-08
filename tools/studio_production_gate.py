"""AHOS Studio-16: evidence-based production gate (read only).

A poster/cropped images never qualify as independent 3D models or animation.
Use --level storyboard | preview | professional. Exit 0 only when that level
has verifiable required assets. No paid service, generation or edits.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROSTER = Path("studio/reference/owner_accepted_roster_v1")
IDS = ("aden", "kaan", "esra", "ahmet", "esma", "harun", "veysel",
       "oznur", "salih", "medine", "davut", "fatos", "emos",
       "berzan", "aras", "ramin")
STAGES = ("model_sheet", "expression_sheet", "mesh_3d", "rig",
          "animation", "voice", "lipsync")
REQUIRED_FOR_PRO = ("model_sheet", "expression_sheet", "mesh_3d",
                    "rig", "animation", "voice", "lipsync")

def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

def json_file(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))

def assess(root: Path = ROOT, level: str = "professional") -> dict:
    """Report verified evidence; never treat status claims as production assets."""
    if level not in ("storyboard", "preview", "professional"):
        raise ValueError("unsupported level")
    issues = []
    warnings = []
    folder = root / ROSTER
    manifest_path = folder / "manifest.json"
    poster = folder / "AHOS_Studio16_Approved_Poster.png"
    if not manifest_path.is_file():
        issues.append("roster_manifest_missing")
        return {"level": level, "pass": False, "roster_valid": False,
                "verified_characters": 0, "issues": issues, "warnings": warnings}
    try:
        manifest = json_file(manifest_path)
    except (ValueError, OSError):
        issues.append("roster_manifest_invalid")
        return {"level": level, "pass": False, "roster_valid": False,
                "verified_characters": 0, "issues": issues, "warnings": warnings}
    if manifest.get("status") != "ROSTER_POSTER_OWNER_ACCEPTED":
        issues.append("roster_not_owner_accepted")
    chars = manifest.get("characters", [])
    if tuple(c.get("id") for c in chars) != IDS:
        issues.append("roster_character_ids_mismatch")
    if not poster.is_file() or sha256(poster) != manifest.get("source_sha256"):
        issues.append("poster_hash_invalid")
    valid = 0
    for row in chars:
        ident = row.get("id")
        if ident not in IDS:
            continue
        expected_name = f"characters/{IDS.index(ident)+1:02d}_{ident}.png"
        if row.get("file") != expected_name:
            issues.append(f"unsafe_or_wrong_filename:{ident}")
            continue
        pic = folder / expected_name
        if not pic.is_file() or sha256(pic) != row.get("sha256"):
            issues.append(f"crop_missing_or_hash_invalid:{ident}")
            continue
        if row.get("status") != "POSTER_CROP_NOT_INDEPENDENT_MODEL":
            issues.append(f"crop_mislabeled:{ident}")
            continue
        valid += 1
    if valid != 16:
        issues.append(f"verified_crops:{valid}/16")
    roster_valid = not issues

    if level == "storyboard":
        # A visual roster is sufficient only for a roster reference, not the show.
        return {"level": level, "pass": roster_valid,
                "roster_valid": roster_valid, "verified_characters": valid,
                "issues": issues, "warnings": ["poster_is_not_a_rig_or_model_sheet"]}

    # Character animation provenance must be recorded per character in the studio,
    # and each reference file must be hash-verified before it counts.
    registry = root / "studio/production/verified-assets.json"
    evidence = {}
    if registry.is_file():
        try:
            evidence = json_file(registry)
        except (ValueError, OSError):
            issues.append("asset_registry_invalid")
    records = evidence.get("characters", {}) if isinstance(evidence, dict) else {}
    ready = {stage: 0 for stage in STAGES}
    for ident in IDS:
        record = records.get(ident, {})
        for stage in STAGES:
            asset = record.get(stage, {})
            rel = asset.get("path") if isinstance(asset, dict) else None
            digest = asset.get("sha256") if isinstance(asset, dict) else None
            if not isinstance(rel, str) or not isinstance(digest, str):
                continue
            rel_path = Path(rel)
            if rel_path.is_absolute() or ".." in rel_path.parts:
                issues.append(f"unsafe_asset_path:{ident}:{stage}")
                continue
            target = (root / rel_path).resolve()
            if root.resolve() not in target.parents or not target.is_file():
                issues.append(f"missing_asset:{ident}:{stage}")
                continue
            if sha256(target) != digest:
                issues.append(f"asset_hash_mismatch:{ident}:{stage}")
                continue
            # Prevent a poster crop from masquerading as a full rig/mesh/model.
            if ROSTER in target.relative_to(root.resolve()).parents:
                issues.append(f"roster_crop_not_production_asset:{ident}:{stage}")
                continue
            ready[stage] += 1
    # Preview still requires independently verified animation for Aden & Kaan.
    required = ("animation", "voice") if level == "preview" else REQUIRED_FOR_PRO
    threshold = 2 if level == "preview" else 16
    for stage in required:
        if ready[stage] < threshold:
            issues.append(f"{stage}_evidence_insufficient:{ready[stage]}/{threshold}")
    if level == "professional":
        film_path = root / "deliverables/S01E001-PROFESSIONAL/S01E001.mp4"
        if not film_path.is_file():
            issues.append("professional_episode_video_missing")
        elif shutil.which("ffprobe") is None:
            issues.append("ffprobe_unavailable")
        else:
            try:
                probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams",
                    "v:0", "-show_entries", "stream=codec_name,width,height",
                    "-of", "json", str(film_path)], capture_output=True, text=True,
                    timeout=15, check=True)
                streams = json.loads(probe.stdout).get("streams", [])
                if not streams or streams[0].get("width", 0) < 1920 or streams[0].get("height", 0) < 1080:
                    issues.append("professional_video_resolution_insufficient")
            except (OSError, ValueError, subprocess.SubprocessError):
                issues.append("professional_video_probe_failed")
    return {"level": level, "pass": roster_valid and not issues,
            "roster_valid": roster_valid, "verified_characters": valid,
            "verified_stage_assets": ready, "issues": issues,
            "warnings": ["A passing file gate does not replace creative human QA."]}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--level", choices=("storyboard", "preview", "professional"),
                        default="professional")
    parser.add_argument("--repo", type=Path, default=ROOT)
    parser.add_argument("--report", type=Path, help="Optional JSON output location")
    args = parser.parse_args()
    report = assess(args.repo, args.level)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered + "\n", encoding="utf-8")
    return 0 if report["pass"] else 2

if __name__ == "__main__":
    raise SystemExit(main())
