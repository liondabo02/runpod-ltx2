"""AHOS Studio Ops - `edit` worker: assemble shots into one film (ffmpeg).

    python tools/studio_ops/edit.py --job-dir DIR --episode S01E000 \
        --shots a.mp4 b.mp4 ... [--out FILE] [--evidence JSON]

Concatenates approved shot clips in order, verifies every stream with ffprobe and
writes the episode file plus an edit manifest (order, durations, sha256).
Zero cost; no re-encode of the video stream (copy), audio is kept as-is.
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


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def probe(path: Path) -> dict:
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
    parser.add_argument("--job-dir", required=True)
    parser.add_argument("--episode", default="S01E000")
    parser.add_argument("--shots", nargs="+", required=True)
    parser.add_argument("--out")
    parser.add_argument("--evidence")
    ns = parser.parse_args(argv)

    job = Path(ns.job_dir).resolve()
    shots = [Path(s) if Path(s).is_absolute() else (job / s) for s in ns.shots]
    missing = [str(s) for s in shots if not s.is_file()]
    if missing:
        report = {"schema": "ahos.edit-manifest.v1", "status": "BLOCKED",
                  "error": "missing shots", "missing": missing}
        if ns.evidence:
            Path(ns.evidence).write_text(json.dumps(report, indent=2), encoding="utf-8")
        print("EDIT_BLOCKED missing=%d" % len(missing))
        return 2

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print("EDIT_BLOCKED ffmpeg_missing")
        return 2

    listing = job / ("%s-concat.txt" % ns.episode)
    listing.write_text("".join("file '%s'\n" % s.as_posix() for s in shots), encoding="utf-8")
    target = Path(ns.out) if ns.out else (job / ("%s-final.mp4" % ns.episode))
    target.parent.mkdir(parents=True, exist_ok=True)

    run = subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                          "-i", str(listing), "-c:v", "copy", "-c:a", "aac",
                          "-strict", "-2", str(target)],
                         capture_output=True, text=True, timeout=1800)
    info = probe(target) if run.returncode == 0 and target.is_file() else {}
    planned = round(sum(float(probe(s).get("duration") or 0.0) for s in shots), 3)
    status = "PASSED" if info.get("duration") else "FAILED"

    manifest = {
        "schema": "ahos.edit-manifest.v1",
        "episode": ns.episode,
        "shots": [{"path": str(s), "sha256": sha(s),
                   "duration": round(float(probe(s).get("duration") or 0.0), 3)} for s in shots],
        "planned_duration": planned,
        "output": str(target),
        "output_sha256": sha(target) if target.is_file() else None,
        "duration": round(float(info.get("duration") or 0.0), 3),
        "resolution": "%sx%s" % (info.get("width"), info.get("height")),
        "fps": info.get("fps"),
        "has_audio": bool(info.get("has_audio")),
        "status": status,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    if ns.evidence:
        Path(ns.evidence).parent.mkdir(parents=True, exist_ok=True)
        Path(ns.evidence).write_text(json.dumps(manifest, indent=2, ensure_ascii=False),
                                     encoding="utf-8")
    print("EDIT_%s shots=%d duration=%.2fs planned=%.2fs audio=%s"
          % (status, len(shots), manifest["duration"], planned, manifest["has_audio"]))
    return 0 if status == "PASSED" else 2


if __name__ == "__main__":
    sys.exit(main())
