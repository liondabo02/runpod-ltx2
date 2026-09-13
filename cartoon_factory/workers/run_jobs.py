from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str], stdin: str | None = None) -> None:
    subprocess.run(cmd, input=stdin, text=True, check=True)


def synthesize_tts(job: dict) -> None:
    voice_dir = Path(os.getenv("PIPER_VOICES_DIR", ROOT / "assets" / "voices"))
    model = voice_dir / f"{job['character_id']}.onnx"
    if not model.exists():
        raise FileNotFoundError(f"Missing Piper voice model: {model}")
    out = ROOT / "output" / CURRENT_EPISODE / job["output"]
    out.parent.mkdir(parents=True, exist_ok=True)
    run([os.getenv("PIPER_BIN", "piper"), "--model", str(model), "--output_file", str(out)], job["text"])


def lipsync(job: dict) -> None:
    rhubarb = os.getenv("RHUBARB_BIN", "rhubarb")
    wav = ROOT / "output" / CURRENT_EPISODE / job["output"]
    json_out = wav.with_suffix(".mouth.json")
    run([rhubarb, "-f", "json", "-o", str(json_out), str(wav)])


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python workers/run_jobs.py <episode_id>")
    global CURRENT_EPISODE
    CURRENT_EPISODE = sys.argv[1]
    jobs_path = ROOT / "output" / CURRENT_EPISODE / "jobs.json"
    jobs = json.loads(jobs_path.read_text(encoding="utf-8"))
    for job in jobs.get("tts", []):
        synthesize_tts(job)
        lipsync(job)
    print(json.dumps({"ok": True, "tts_jobs": len(jobs.get('tts', [])), "next": "render"}))


CURRENT_EPISODE = ""
if __name__ == "__main__":
    main()
