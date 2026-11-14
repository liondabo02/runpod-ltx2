"""AHOS Studio OS - `voice` backend v0.1 (free neural TTS via edge-tts).

    python tools/studio_backends/voice.py --plan plan.json --job-dir DIR --evidence EV.json

Licence honesty: edge-tts is a free client for Microsoft's read-aloud service,
so each voice profile carries `license_status`; commercial_license_verified is
true only when every profile is approved.
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
PROFILES = ROOT / "studio" / "audio" / "voice-profiles.json"
APPROVED = {"approved", "own", "verified"}


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def which(name):
    return os.environ.get(name.upper().replace("-", "_") + "_EXE") or shutil.which(name)


def cast_ids(plan):
    out = []
    for item in plan.get("cast") or []:
        out.append(item.get("id") if isinstance(item, dict) else str(item))
    return [c for c in out if c]


def load_profiles():
    if not PROFILES.is_file():
        return {}
    return json.loads(PROFILES.read_text(encoding="utf-8")).get("profiles", {})


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--job-dir", required=True)
    parser.add_argument("--evidence", required=True)
    ns = parser.parse_args(argv)

    job = Path(ns.job_dir).resolve()
    plan = json.loads(Path(ns.plan).read_text(encoding="utf-8-sig"))
    out = job / "voice"
    out.mkdir(parents=True, exist_ok=True)

    language = str(plan.get("language") or "tr").lower()
    lines = plan.get("dialogue") or plan.get("lines") or {}
    profiles = load_profiles()
    tts, ffmpeg, ffprobe = which("edge-tts"), which("ffmpeg"), which("ffprobe")
    artifacts, checks, blocked = [], {}, []
    if not tts:
        blocked.append({"code": "TTS_MISSING",
                        "remediation": "pip install edge-tts (free)"})
    if not ffmpeg:
        blocked.append({"code": "FFMPEG_MISSING", "remediation": "install ffmpeg"})

    for cid in cast_ids(plan):
        profile = profiles.get(cid, {}).get(language)
        if not profile:
            blocked.append({"component": cid, "code": "VOICE_PROFILE_MISSING",
                            "remediation": "add %s/%s to studio/audio/voice-profiles.json"
                                           % (cid, language)})
            continue
        text = lines.get(cid) if isinstance(lines, dict) else None
        text = text or "%s için örnek replik." % cid
        target = out / ("%s-%s.wav" % (cid, language))
        raw = out / ("%s-%s.mp3" % (cid, language))
        target.unlink(missing_ok=True)
        try:
            tts_run = subprocess.run([tts, "--voice", profile["voice_id"], "--text", text,
                                      "--write-media", str(raw)],
                                     capture_output=True, text=True, timeout=180)
        except subprocess.TimeoutExpired:
            blocked.append({"component": cid, "code": "TTS_TIMEOUT",
                            "remediation": "edge-tts did not answer in 180s"})
            continue
        if tts_run.returncode != 0 or not raw.is_file():
            blocked.append({"component": cid, "code": "TTS_FAILED",
                            "remediation": (tts_run.stderr or "no media written")[-300:].strip()})
            continue
        try:
            subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", str(raw),
                            "-ar", "24000", "-ac", "1", "-c:a", "pcm_s16le", str(target)],
                           check=True, capture_output=True, text=True, timeout=120)
        except subprocess.CalledProcessError as exc:
            blocked.append({"component": cid, "code": "WAV_CONVERT_FAILED",
                            "remediation": (exc.stderr or "")[-200:].strip()})
            continue
        raw.unlink(missing_ok=True)

        if not target.is_file() or target.read_bytes()[:4] != b"RIFF":
            blocked.append({"component": cid, "code": "WAV_INVALID",
                            "remediation": "TTS output was not a WAV container"})
            continue
        duration = 0.0
        if ffprobe:
            probe = subprocess.run([ffprobe, "-v", "error", "-show_entries",
                                    "format=duration", "-of", "json", str(target)],
                                   capture_output=True, text=True)
            if probe.returncode == 0:
                duration = float(json.loads(probe.stdout)["format"]["duration"])
        if duration <= 0.2:
            blocked.append({"component": cid, "code": "AUDIO_TOO_SHORT",
                            "remediation": "duration %.2fs" % duration})
            continue

        checks[cid] = {"voice_id": profile["voice_id"], "language": language,
                       "duration_seconds": round(duration, 3),
                       "license_status": profile.get("license_status", "review_required"),
                       "text": text}
        artifacts.append({"kind": "voice", "cast": cid,
                          "path": str(target.relative_to(job)).replace("\\", "/"),
                          "bytes": target.stat().st_size, "sha256": sha(target)})

    status = "PASSED" if (artifacts and not blocked) else "BLOCKED"
    licensed = status == "PASSED" and all(
        str(e.get("license_status", "")).lower() in APPROVED for e in checks.values())
    evidence = {
        "stage": "voice", "status": status, "cost_eur": 0,
        "commercial_license_verified": licensed,
        "license_basis": "edge-tts free endpoint; licence status from the voice profile",
        "cast_ids": cast_ids(plan), "language": language,
        "artifacts": artifacts, "checks": checks, "blocked": blocked,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    Path(ns.evidence).parent.mkdir(parents=True, exist_ok=True)
    Path(ns.evidence).write_text(json.dumps(evidence, indent=2, ensure_ascii=False),
                                 encoding="utf-8")
    print("VOICE_BACKEND_%s cast=%s artifacts=%d blocked=%d"
          % (status, ",".join(cast_ids(plan)), len(artifacts), len(blocked)))
    return 0 if status == "PASSED" else 2


if __name__ == "__main__":
    sys.exit(main())
