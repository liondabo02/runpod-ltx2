"""AHOS Studio Ops - `distribution` worker: subtitles + per-language delivery.

    python tools/studio_ops/distribution.py --episode-mp4 FILE --dialogue "text" \
        --language tr --out DIR [--evidence OUT.json]

Splits the dialogue into proportional subtitle cues for the film duration, writes
an SRT and copies the film into <out>/<language>/. Kurmancî is emitted as a track
marked pending until a reference voice exists - never silently faked.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PENDING_LANGS = {"ku", "kmr"}   # Kurmancî: needs a reference voice / human actor


def duration_of(path: Path) -> float:
    exe = shutil.which("ffprobe")
    if not exe:
        return 0.0
    run = subprocess.run([exe, "-v", "error", "-show_entries", "format=duration",
                          "-of", "json", str(path)], capture_output=True, text=True)
    if run.returncode != 0:
        return 0.0
    try:
        return float(json.loads(run.stdout)["format"]["duration"])
    except (ValueError, KeyError):
        return 0.0


def cue_text(text: str):
    parts = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text or "") if part.strip()]
    return parts or ([text.strip()] if (text or "").strip() else [])


def srt(cues, duration):
    if not cues or duration <= 0:
        return ""
    span = duration / len(cues)
    lines = []
    for index, cue in enumerate(cues, start=1):
        start = (index - 1) * span
        end = duration if index == len(cues) else index * span

        def stamp(seconds):
            hours, rest = divmod(seconds, 3600)
            minutes, secs = divmod(rest, 60)
            return ("%02d:%02d:%06.3f" % (int(hours), int(minutes), secs)).replace(".", ",")

        lines.append("%d\n%s --> %s\n%s\n" % (index, stamp(start), stamp(end), cue))
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--episode-mp4", required=True)
    parser.add_argument("--dialogue", required=True)
    parser.add_argument("--language", default="tr")
    parser.add_argument("--out", required=True)
    parser.add_argument("--evidence")
    ns = parser.parse_args(argv)

    film = Path(ns.episode_mp4).resolve()
    out = Path(ns.out).resolve()
    lang = ns.language.lower()
    findings = []
    if not film.is_file():
        print("DISTRIBUTION_BLOCKED film_missing")
        return 2

    duration = duration_of(film)
    cues = cue_text(ns.dialogue)
    lang_dir = out / lang
    lang_dir.mkdir(parents=True, exist_ok=True)
    delivered = lang_dir / ("%s-%s.mp4" % (film.stem, lang))
    if film.resolve() != delivered.resolve():
        shutil.copy2(film, delivered)
    subtitle = lang_dir / ("%s-%s.srt" % (film.stem, lang))
    text = srt(cues, duration)
    if text:
        subtitle.write_text(text, encoding="utf-8")
    else:
        findings.append({"level": "error", "text": "no subtitle cues produced"})

    if lang in PENDING_LANGS:
        findings.append({"level": "warn",
                         "text": "Kurmancî audio is pending: needs a reference voice "
                                 "or a human actor; subtitle track only"})

    report = {
        "schema": "ahos.delivery-manifest.v1",
        "film": str(film), "language": lang,
        "duration_seconds": round(duration, 3),
        "cues": len(cues),
        "video": str(delivered), "subtitles": str(subtitle),
        "audio_status": "pending" if lang in PENDING_LANGS else "available",
        "status": "PASSED" if not [f for f in findings if f["level"] == "error"] else "FAILED",
        "findings": findings,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    if ns.evidence:
        Path(ns.evidence).parent.mkdir(parents=True, exist_ok=True)
        Path(ns.evidence).write_text(json.dumps(report, indent=2, ensure_ascii=False),
                                     encoding="utf-8")
    for finding in findings:
        print("  [%s] %s" % (finding["level"], finding["text"]))
    print("DISTRIBUTION_%s lang=%s cues=%d duration=%.2fs audio=%s"
          % (report["status"], lang, len(cues), duration, report["audio_status"]))
    return 0 if report["status"] == "PASSED" else 2


if __name__ == "__main__":
    sys.exit(main())
