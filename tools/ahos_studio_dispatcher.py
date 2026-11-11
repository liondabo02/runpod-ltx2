"""Fail-closed, zero-spend AHOS production adapter dispatcher.

A backend is NOT a named agent or prompt. It is an executable reviewed script
under tools/studio_backends/ which writes actual artifacts plus hash evidence.
No real backend installed = BLOCKED, never synthetic professional success.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

from ahos_text_to_cartoon import ROOT

STAGES = (
    "character_model", "rig", "animation", "voice", "lipsync",
    "scene", "render", "qa",
)
KINDS = {
    "character_model": "character_model",
    "rig": "rig",
    "animation": "animation",
    "voice": "voice",
    "lipsync": "lipsync",
    "scene": "scene",
    "render": "film",
    "qa": "quality_report",
}
EXTENSIONS = {
    "character_model": (".blend", ".glb"),
    "rig": (".blend", ".glb"),
    "animation": (".blend", ".glb", ".fbx"),
    "voice": (".wav",),
    "lipsync": (".json",),
    "scene": (".blend", ".glb"),
    "render": (".mp4",),
    "qa": (".json",),
}
CONFIG = Path("studio/pipeline/production-backends.json")


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fd:
        for block in iter(lambda: fd.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_backends(root: Path = ROOT) -> dict:
    path = root / CONFIG
    if not path.is_file():
        return {"schema": "ahos.production.adapters.v1", "stages": {}}
    config = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or config.get("schema") != "ahos.production.adapters.v1":
        raise ValueError("Backend configuration schema mismatch")
    if not isinstance(config.get("stages"), dict):
        raise ValueError("Backend stages must be object")
    return config


def capabilities(root: Path = ROOT) -> dict:
    reg = load_backends(root)
    available = {}
    for stage in STAGES:
        setup = reg["stages"].get(stage)
        valid = isinstance(setup, dict) and setup.get("cost_eur") == 0
        script = setup.get("script", "") if valid else ""
        if not re.fullmatch(r"tools/studio_backends/[A-Za-z0-9_/-]+\.py", script):
            valid = False
        script_path = (root / script).resolve() if valid else None
        if script_path is None or root.resolve() not in script_path.parents or not script_path.is_file():
            valid = False
        available[stage] = {
            "installed": bool(valid),
            "script": script if valid else None,
            "reason": "registered_free_backend" if valid else "no_verified_zero_euro_backend",
        }
    return {
        "schema": "ahos.production.capabilities.v1",
        "stages": available,
        "all_backends_installed": all(x["installed"] for x in available.values()),
        "production_ready": False,
    }


def _verified_artifact(job_dir: Path, stage: str, item: dict) -> dict:
    if not isinstance(item, dict) or item.get("kind") != KINDS[stage]:
        raise ValueError(f"{stage}: required artifact kind missing")
    rel = item.get("path")
    sha = item.get("sha256")
    if not isinstance(rel, str) or not rel or not isinstance(sha, str) or len(sha) != 64:
        raise ValueError(f"{stage}: path/hash missing")
    candidate = Path(rel)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"{stage}: unsafe path")
    path = (job_dir / candidate).resolve()
    if job_dir.resolve() not in path.parents or not path.is_file():
        raise ValueError(f"{stage}: file outside job or missing")
    if path.suffix.lower() not in EXTENSIONS[stage]:
        raise ValueError(f"{stage}: unexpected extension")
    if path.stat().st_size < (1000 if stage != "lipsync" and stage != "qa" else 20):
        raise ValueError(f"{stage}: trivially small artifact")
    if digest(path) != sha.lower():
        raise ValueError(f"{stage}: artifact hash mismatch")
    if path.suffix.lower() == ".blend" and not path.open("rb").read(7) == b"BLENDER":
        raise ValueError(f"{stage}: invalid Blender file signature")
    if path.suffix.lower() == ".glb" and not path.open("rb").read(4) == b"glTF":
        raise ValueError(f"{stage}: invalid glTF binary")
    if stage == "lipsync":
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data.get("visemes"), list) or len(data["visemes"]) < 2:
            raise ValueError("No real viseme sequence")
    if stage == "qa":
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("technical_pass") is not True or data.get("creative_approved") is not True:
            raise ValueError("Professional QA and creative approval not present")
    if stage == "voice":
        import wave
        with wave.open(str(path), "rb") as wav:
            if wav.getnframes() < wav.getframerate() // 2:
                raise ValueError("Voice track too short")
            if wav.getnchannels() < 1:
                raise ValueError("Voice track channels invalid")
    if stage == "render":
        import shutil
        ffprobe = shutil.which("ffprobe")
        if ffprobe is None:
            raise ValueError("No ffprobe")
        probe = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries",
             "stream=codec_type,width,height,r_frame_rate", "-of", "json", str(path)],
            capture_output=True, text=True, timeout=20, check=True,
        )
        info = json.loads(probe.stdout)
        streams = info.get("streams", [])
        video = [x for x in streams if x.get("codec_type") == "video"]
        audio = [x for x in streams if x.get("codec_type") == "audio"]
        if not video or not audio:
            raise ValueError("Film must have video AND audio")
        if video[0].get("width", 0) < 1920 or video[0].get("height", 0) < 1080:
            raise ValueError("Full-HD film expected")
    return {"path": rel, "sha256": sha, "bytes": path.stat().st_size}


def dispatch_stage(plan: dict, job_dir: Path, stage: str, root: Path = ROOT,
                   timeout_seconds: int = 180) -> dict:
    """Run exactly one registered stage (P12-A standalone backend proof)."""
    if stage not in STAGES:
        raise ValueError(f"unknown stage: {stage}")
    if not 5 <= timeout_seconds <= 1800:
        raise ValueError("Backend timeout must be 5-1800 seconds")
    job_dir = job_dir.resolve()
    job_dir.mkdir(parents=True, exist_ok=True)
    config = load_backends(root)
    report = {
        "schema": "ahos.production.dispatch-stage.v1",
        "status": "BLOCKED",
        "production_ready": False,
        "cost_eur": 0,
        "cast": plan.get("cast", []),
        "stages": [],
        "blockers": [],
    }
    plan_path = job_dir / "story-plan.json"
    if not plan_path.is_file():
        plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    setup = config["stages"].get(stage)
    caps = capabilities(root)["stages"][stage]
    if not caps["installed"]:
        report["stages"].append({"stage": stage, "status": "BLOCKED", "reason": caps["reason"]})
        report["blockers"].append(f"{stage}: {caps['reason']}")
        (job_dir / f"production-dispatch-{stage}.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report
    script = (root / setup["script"]).resolve()
    evidence = job_dir / f"{stage}-evidence.json"
    args = [sys.executable, str(script), "--plan", str(plan_path),
            "--job-dir", str(job_dir), "--evidence", str(evidence)]
    try:
        run = subprocess.run(args, cwd=root, capture_output=True, text=True,
                             timeout=timeout_seconds, check=False)
        if run.returncode:
            raise ValueError(f"backend exit={run.returncode}: {run.stderr[-450:]}")
        if not evidence.is_file():
            raise ValueError("backend produced no evidence")
        data = json.loads(evidence.read_text(encoding="utf-8"))
        if data.get("stage") != stage or data.get("status") != "PASSED":
            raise ValueError("backend did not certify this exact stage")
        if data.get("cost_eur") != 0 or data.get("commercial_license_verified") is not True:
            raise ValueError("zero-cost and commercial license proof required")
        artifacts = data.get("artifacts")
        if not isinstance(artifacts, list) or not artifacts:
            raise ValueError("no real artifacts")
        verified = [_verified_artifact(job_dir, stage, x) for x in artifacts]
        report["stages"].append({"stage": stage, "status": "VERIFIED_TECHNICAL",
                                 "artifacts": verified})
        report["status"] = "VERIFIED_TECHNICAL"
    except (ValueError, OSError, TimeoutError, subprocess.TimeoutExpired,
            subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        report["stages"].append({"stage": stage, "status": "BLOCKED", "reason": str(exc)[:600]})
        report["blockers"].append(f"{stage}: {str(exc)[:240]}")
    (job_dir / f"production-dispatch-{stage}.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def dispatch(plan: dict, job_dir: Path, root: Path = ROOT, timeout_seconds: int = 180) -> dict:
    """Attempt every registered stage in order, stop truthfully at first blocker."""
    if not 5 <= timeout_seconds <= 1800:
        raise ValueError("Backend timeout must be 5-1800 seconds")
    job_dir = job_dir.resolve()
    job_dir.mkdir(parents=True, exist_ok=True)
    config = load_backends(root)
    report = {
        "schema": "ahos.production.dispatch.v1",
        "status": "BLOCKED",
        "production_ready": False,
        "cost_eur": 0,
        "cast": plan.get("cast", []),
        "stages": [],
        "blockers": [],
    }
    plan_path = job_dir / "story-plan.json"
    if not plan_path.is_file():
        plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    for stage in STAGES:
        setup = config["stages"].get(stage)
        caps = capabilities(root)["stages"][stage]
        if not caps["installed"]:
            report["stages"].append({"stage": stage, "status": "BLOCKED", "reason": caps["reason"]})
            report["blockers"].append(f"{stage}: {caps['reason']}")
            break
        script = (root / setup["script"]).resolve()
        evidence = job_dir / f"{stage}-evidence.json"
        args = [sys.executable, str(script), "--plan", str(plan_path),
                "--job-dir", str(job_dir), "--evidence", str(evidence)]
        try:
            run = subprocess.run(args, cwd=root, capture_output=True, text=True,
                                 timeout=timeout_seconds, check=False)
            if run.returncode:
                raise ValueError(f"backend exit={run.returncode}: {run.stderr[-450:]}")
            if not evidence.is_file():
                raise ValueError("backend produced no evidence")
            data = json.loads(evidence.read_text(encoding="utf-8"))
            if data.get("stage") != stage or data.get("status") != "PASSED":
                raise ValueError("backend did not certify this exact stage")
            if data.get("cost_eur") != 0 or data.get("commercial_license_verified") is not True:
                raise ValueError("zero-cost and commercial license proof required")
            artifacts = data.get("artifacts")
            if not isinstance(artifacts, list) or not artifacts:
                raise ValueError("no real artifacts")
            verified = [_verified_artifact(job_dir, stage, x) for x in artifacts]
            report["stages"].append({"stage": stage, "status": "VERIFIED_TECHNICAL",
                                     "artifacts": verified})
        except (ValueError, OSError, TimeoutError, subprocess.TimeoutExpired,
                subprocess.CalledProcessError, json.JSONDecodeError) as exc:
            report["stages"].append({"stage": stage, "status": "BLOCKED", "reason": str(exc)[:600]})
            report["blockers"].append(f"{stage}: {str(exc)[:240]}")
            break
    else:
        # Not enough to pass a human/production approval by merely emitting files.
        # The repository-wide professional gate is a separate authority.
        from studio_production_gate import assess
        official = assess(root, level="professional")
        if official["pass"] is True:
            report["status"] = "READY_FOR_OWNER_FINAL_REVIEW"
            report["blockers"] = []
        else:
            report["blockers"].append("official_production_gate_failed")
            report["official_gate_issues"] = official.get("issues", [])
    (job_dir / "production-dispatch.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--plan", type=Path, required=True)
    p.add_argument("--job-dir", type=Path, required=True)
    p.add_argument("--root", type=Path, default=ROOT)
    p.add_argument("--stage", choices=STAGES)
    args = p.parse_args()
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    if args.stage:
        result = dispatch_stage(plan, args.job_dir, args.stage, args.root)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["status"] == "VERIFIED_TECHNICAL" else 2
    result = dispatch(plan, args.job_dir, args.root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "READY_FOR_OWNER_FINAL_REVIEW" else 2


if __name__ == "__main__":
    raise SystemExit(main())
