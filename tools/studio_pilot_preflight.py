"""Read-only offline readiness check for the proposed S01E001 30-second pilot.

This checks production inputs and SHA proofs. It never renders, spends, or
writes to the private animation database.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_SHEETS = {
    "aden-turnaround": "aden-turnaround-v2-kontext-seed-501.png",
    "aden-expressions": "aden-expressions-v2-kontext-seed-502.png",
    "kaan-turnaround": "kaan-turnaround-v2-kontext-seed-503.png",
    "kaan-expressions": "kaan-expressions-v2-kontext-seed-504.png",
}


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (ValueError, OSError):
        return {}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(part)
    return digest.hexdigest()


def evaluate(root: Path = ROOT) -> dict:
    """No writes and no network calls; status is intentionally fail-closed."""
    plan = _read_json(root / "workflows" / "S01E001-pilot-30s-plan.json")
    issues: list[str] = []
    scenes = plan.get("scenes") or []
    clips = [clip for scene in scenes for clip in (scene.get("clips") or [])]
    if len(scenes) != 3 or len(clips) != 6:
        issues.append("expected_three_scenes_six_clips")
    ids = [clip.get("clip_id") for clip in clips]
    if len(set(ids)) != len(ids) or any(not ident for ident in ids):
        issues.append("duplicate_or_missing_clip_ids")
    if sum(clip.get("duration_seconds", 0) for clip in clips) != 30:
        issues.append("duration_not_30s")
    if any(clip.get("duration_seconds", 0) > 5 for clip in clips):
        issues.append("clip_exceeds_5s_free_space_cap")
    characters = {
        name: _read_json(root / "characters" / (name + ".json"))
        for name in ("aden", "kaan")
    }
    for name, gender, age in (("aden", "female", 3), ("kaan", "male", 1)):
        char = characters[name]
        if char.get("character_id") != name or char.get("gender") != gender or char.get("age_years") != age:
            issues.append("character_identity_mismatch:" + name)
    cast = set(plan.get("cast_ids") or [])
    if cast != {"aden", "kaan"} or any(not set(c.get("cast_ids") or []).issubset(cast) for c in clips):
        issues.append("uncanonical_cast")
    for clip in clips:
        for line in clip.get("dialogue") or []:
            if line.get("character_id") not in cast:
                issues.append("dialogue_speaker_not_cast")
            if line.get("character_id") == "kaan" and len((line.get("text") or "").split()) > 2:
                issues.append("kaan_adult_speech")
    if "koruyucu abi" in characters["aden"].get("body_language", {}).get("eye_contact", "").casefold():
        issues.append("aden_old_male_role_text")
    audio_root = root / "control_plane_v2" / "runtime" / "private" / "animation-studio" / "audio" / "core-voices"
    voice = {
        name: {
            "tr": (audio_root / name / "tr.wav").is_file(),
            "en": (audio_root / name / "reference-en.wav").is_file(),
        }
        for name in cast
    }
    sheet_root = root / "control_plane_v2" / "runtime" / "private" / "animation-studio" / "model-sheets"
    manifest = _read_json(sheet_root / "model-sheets-v2-manifest.local.json")
    records = manifest.get("steps") or {}
    sheets = {}
    for ident, filename in REQUIRED_SHEETS.items():
        record = records.get(ident) or {}
        path = sheet_root / filename
        verified = (
            record.get("status") == "ok" and path.is_file()
            and record.get("sha256") == _sha256(path)
        )
        sheets[ident] = {"verified": verified, "status": record.get("status") or "missing"}
    story = _read_json(root / "control_plane_v2" / "runtime" / "private"
                       / "animation-studio" / "episodes" / "S01E001" / "story-packet.local.json")
    story_approved = bool(story.get("owner_approved"))
    approval = _read_json(root / "control_plane_v2" / "runtime" / "private"
                          / "animation-studio" / "pilot-owner-approval.local.json")
    pilot_approved = (approval.get("episode_id") == "S01E001"
                      and approval.get("plan_schema") == plan.get("schema")
                      and approval.get("approved") is True)
    assets_ok = all(item["verified"] for item in sheets.values())
    planning_ready = bool(plan) and not issues
    return {
        "episode": "S01E001",
        "planning_ready": planning_ready,
        "scenes": len(scenes),
        "clips": len(clips),
        "duration_seconds": sum(c.get("duration_seconds", 0) for c in clips),
        "issues": issues,
        "voice_assets": voice,
        "v2_sheets": sheets,
        "story_packet_owner_approved": story_approved,
        "pilot_owner_approved": pilot_approved,
        "render_allowed": bool(planning_ready and assets_ok and pilot_approved),
        "full_episode_allowed": bool(planning_ready and assets_ok and pilot_approved and story_approved),
        "notice": "Preflight only; neither render nor paid service was invoked.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    report = evaluate(args.root)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["planning_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
