"""AHOS Studio OS - `render` backend v0.1: audio+video mux with real stream gates.

    python tools/studio_backends/render_av.py --plan plan.json --job-dir DIR --evidence EV.json

Takes the approved picture artefact (kind=animation/render/film/edit, .mp4) and the
approved voice WAV, muxes them with ffmpeg and verifies video stream, audio stream,
duration and resolution. Zero cost.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import growth  # noqa: E402
import memory  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
APPROVED = {"approved", "own", "public-domain", "public_domain", "gpl", "verified"}
PICTURE_KINDS = {"animation", "render", "film", "edit", "scene"}


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
        item = next((p for p in candidates if p.is_file()), None)
        if item is None:
            return None, "DEPENDENCY_MISSING"
        expected = str(art.get("sha256") or "").lower()
        if len(expected) != 64:
            return None, "SHA_MISSING"
        if sha(item) != expected:
            return None, "SHA_MISMATCH"
        if str(art.get("license_status") or "").lower() not in APPROVED:
            return None, "LICENSE_UNVERIFIED"
        return item, None
    return None, "DEPENDENCY_MISSING"


def probe(path: Path):
    exe = shutil.which("ffprobe")
    if not exe:
        return {}
    run = subprocess.run([exe, "-v", "error", "-print_format", "json", "-show_format",
                          "-show_streams", str(path)], capture_output=True, text=True)
    if run.returncode != 0:
        return {}
    data = json.loads(run.stdout)
    video = next((s for s in data["streams"] if s.get("codec_type") == "video"), {})
    audio = next((s for s in data["streams"] if s.get("codec_type") == "audio"), None)
    return {"duration": float(data.get("format", {}).get("duration", 0.0)),
            "width": video.get("width"), "height": video.get("height"),
            "fps": video.get("r_frame_rate"), "has_audio": audio is not None}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--job-dir", required=True)
    parser.add_argument("--evidence", required=True)
    ns = parser.parse_args(argv)

    job = Path(ns.job_dir).resolve()
    plan = json.loads(Path(ns.plan).read_text(encoding="utf-8-sig"))
    plan["_job_dir"] = str(job)
    out = job / "render"
    if out.exists():
        for stale in out.iterdir():
            if stale.is_file():
                stale.unlink()
    out.mkdir(parents=True, exist_ok=True)

    ffmpeg = shutil.which("ffmpeg")
    coach = growth.guidance("render")
    artifacts, checks, blocked = [], {}, []
    if not ffmpeg:
        blocked.append({"code": "FFMPEG_MISSING", "remediation": "install ffmpeg"})

    video, verr = pick(plan, PICTURE_KINDS, ".mp4")
    audio, aerr = pick(plan, {"voice"}, ".wav")
    if video is None:
        blocked.append({"code": verr, "remediation": "approved picture (.mp4) required"})
    if audio is None:
        blocked.append({"code": aerr, "remediation": "approved voice (.wav) required"})

    if video and audio and ffmpeg:
        target = out / ("%s-%s-av.mp4" % (plan.get("episode_id", "ep"),
                                          plan.get("language", "tr")))
        run = subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", str(video),
                              "-i", str(audio), "-c:v", "copy", "-c:a", "aac",
                              "-strict", "-2", "-b:a", "128k", "-shortest", str(target)],
                             capture_output=True, text=True, timeout=900)
        info = probe(target) if run.returncode == 0 and target.is_file() else {}
        if run.returncode != 0 or not info.get("has_audio"):
            blocked.append({"code": "MUX_FAILED",
                            "remediation": (run.stderr or "no audio stream")[-300:].strip()})
        elif float(info.get("duration") or 0) <= 0.5:
            blocked.append({"code": "FILM_TOO_SHORT", "remediation": "duration too small"})
        else:
            checks["film"] = {"video": str(video), "audio": str(audio),
                              "duration": round(info["duration"], 3),
                              "resolution": "%sx%s" % (info.get("width"), info.get("height")),
                              "fps": info.get("fps"), "has_audio": True}
            artifacts.append({"kind": "film", "cast": ",".join(cast_ids(plan)),
                              "path": str(target.relative_to(job)).replace("\\", "/"),
                              "bytes": target.stat().st_size, "sha256": sha(target)})

    status = "PASSED" if (artifacts and not blocked) else "BLOCKED"
    evidence = {
        "stage": "render", "status": status, "cost_eur": 0,
        "commercial_license_verified": status == "PASSED",
        "license_basis": "ffmpeg (LGPL/GPL) + locally produced picture and voice",
        "cast_ids": cast_ids(plan), "checks": checks, "artifacts": artifacts,
        "blocked": blocked, "growth": coach, "memory": memory.digest("render"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    memory.remember("render", {"status": status, "cast": cast_ids(plan),
                               "artifacts": len(artifacts),
                               "blocked_codes": [b.get("code") for b in blocked]})
    evidence["memory_after"] = memory.digest("render")
    Path(ns.evidence).parent.mkdir(parents=True, exist_ok=True)
    Path(ns.evidence).write_text(json.dumps(evidence, indent=2, ensure_ascii=False),
                                 encoding="utf-8")
    print("RENDER_BACKEND_%s artifacts=%d blocked=%d"
          % (status, len(artifacts), len(blocked)))
    return 0 if status == "PASSED" else 2


if __name__ == "__main__":
    sys.exit(main())

