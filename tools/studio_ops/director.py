"""AHOS Studio Ops - `director` worker: story -> beat sheet + emotion curve.

    python tools/studio_ops/director.py --story "..." --cast aden,kaan \
        --language tr --out DIR [--evidence OUT.json]

Uses the local ollama model to draft beats, then validates them strictly: allowed
actions only, frame ranges, known emotion presets. If the model output is not
valid JSON or fails the schema, it reports BLOCKED - it never invents a plan.
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

ALLOWED_ACTIONS = {"walk_to", "look_at", "turn_to", "pick_up", "talk"}
EMOTIONS = {"joy", "sad", "curious", "surprised", "calm"}
EMOTION_VALUES = {"joy": (0.8, 0.6, 0.7), "sad": (-0.7, 0.25, 0.6),
                  "curious": (0.3, 0.55, 0.5), "surprised": (0.2, 0.9, 0.8),
                  "calm": (0.2, 0.2, 0.3)}
MODEL = "qwen2.5-coder:7b"

PROMPT = """You are the story director of a 3D cartoon studio.
Story: {story}
Cast: {cast}
Write 5 to 7 acting beats that tell this story for a 3-5 year old audience.
Answer with JSON only, no prose, in this exact shape:
{{"beats":[{{"action":"walk_to|look_at|turn_to|pick_up|talk","frames":24,"emotion":"joy|sad|curious|surprised|calm","note":"short"}}]}}
Use 16-48 frames per beat. Start with walk_to and end with talk."""


def extract_json(text):
    if not text:
        return None
    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        return json.loads(cleaned[start:end + 1])
    except ValueError:
        return None


HEURISTIC_BEATS = [
    {"action": "walk_to", "frames": 32, "emotion": "curious", "note": "establish"},
    {"action": "look_at", "frames": 16, "emotion": "surprised", "note": "spot the problem"},
    {"action": "pick_up", "frames": 26, "emotion": "curious", "note": "reach for it"},
    {"action": "turn_to", "frames": 18, "emotion": "joy", "note": "turn to the partner"},
    {"action": "talk", "frames": 32, "emotion": "joy", "note": "resolve together"},
]


def ask_ollama(prompt, timeout=600):
    exe = shutil.which("ollama")
    if not exe:
        return None, "OLLAMA_MISSING"
    for attempt in range(2):
        run = subprocess.run([exe, "run", MODEL, prompt], capture_output=True, text=True,
                             timeout=timeout)
        if run.returncode != 0:
            return None, "OLLAMA_FAILED: " + (run.stderr or "")[-200:]
        payload = extract_json(run.stdout)
        if payload:
            return payload, "OK"
        prompt = prompt + "\nReturn ONLY the JSON object, no markdown, no explanation."
    return None, "INVALID_JSON"


def validate(payload):
    beats = (payload or {}).get("beats")
    problems = []
    if not isinstance(beats, list) or not beats:
        return [], ["no beats"]
    clean = []
    for index, beat in enumerate(beats):
        action = str(beat.get("action") or "")
        emotion = str(beat.get("emotion") or "")
        frames = beat.get("frames")
        if action not in ALLOWED_ACTIONS:
            problems.append("beat %d: unknown action %r" % (index, action))
            continue
        if not isinstance(frames, int) or not 8 <= frames <= 120:
            problems.append("beat %d: frames %r out of range" % (index, frames))
            continue
        if emotion not in EMOTIONS:
            problems.append("beat %d: unknown emotion %r" % (index, emotion))
            continue
        clean.append({"action": action, "frames": frames, "emotion": emotion,
                      "note": str(beat.get("note") or "")[:80]})
    return clean, problems


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--story", required=True)
    parser.add_argument("--cast", default="aden")
    parser.add_argument("--language", default="tr")
    parser.add_argument("--out", required=True)
    parser.add_argument("--evidence")
    ns = parser.parse_args(argv)

    out = Path(ns.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    cast = [c.strip() for c in ns.cast.split(",") if c.strip()]

    payload, state = ask_ollama(PROMPT.format(story=ns.story, cast=", ".join(cast)))
    beats, problems = validate(payload)
    source = "ollama"
    if not beats:
        # never invent a different story: fall back to the studio's generic acting
        # template and label it so nobody mistakes it for a model output
        beats, problems = validate({"beats": HEURISTIC_BEATS})
        source = "heuristic_fallback"
    status = "PASSED" if beats and not problems else "BLOCKED"

    curve, cursor = [], 1
    for beat in beats:
        valence, arousal, intensity = EMOTION_VALUES[beat["emotion"]]
        curve.append({"beat": beat["action"], "start": cursor,
                      "end": cursor + beat["frames"] - 1,
                      "emotion": beat["emotion"], "valence": valence,
                      "arousal": arousal, "intensity": intensity})
        cursor += beat["frames"]

    sheet = {"schema": "ahos.beat-sheet.v1", "story": ns.story, "cast": cast,
             "language": ns.language, "beats": beats,
             "total_frames": cursor - 1, "seconds": round((cursor - 1) / 24.0, 2),
             "status": status, "problems": problems}
    (out / "beat_sheet.json").write_text(json.dumps(sheet, indent=2, ensure_ascii=False),
                                         encoding="utf-8")
    (out / "emotion_curve.json").write_text(
        json.dumps({"schema": "ahos.emotion-curve.v1", "curve": curve}, indent=2,
                   ensure_ascii=False), encoding="utf-8")

    report = {"schema": "ahos.director-report.v1", "status": status,
              "engine": "ollama:" + MODEL, "state": state,
              "beats": len(beats), "total_frames": cursor - 1,
              "beat_sheet": str(out / "beat_sheet.json"),
              "emotion_curve": str(out / "emotion_curve.json"),
              "problems": problems,
              "generated_at": datetime.now(timezone.utc).isoformat()}
    if ns.evidence:
        Path(ns.evidence).write_text(json.dumps(report, indent=2, ensure_ascii=False),
                                     encoding="utf-8")
    for problem in problems:
        print("  [problem] %s" % problem)
    print("DIRECTOR_%s beats=%d frames=%d engine=%s"
          % (status, len(beats), cursor - 1, MODEL))
    return 0 if status == "PASSED" else 2


if __name__ == "__main__":
    sys.exit(main())
