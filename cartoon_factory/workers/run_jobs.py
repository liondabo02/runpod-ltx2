from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str], stdin: str | None = None) -> None:
    subprocess.run(cmd, input=stdin, text=True, check=True)


def resolve_voice_model(job: dict) -> Path:
    voice_root = Path(os.getenv("PIPER_VOICES_DIR", ROOT / "assets" / "voices"))
    lang = job.get("language", "tr")
    cid = job["character_id"]
    candidates = [
        voice_root / lang / f"{cid}.onnx",
        voice_root / lang / "default.onnx",
        voice_root / f"{cid}.onnx",
        voice_root / "default.onnx",
    ]
    for model in candidates:
        if model.exists():
            return model
    raise FileNotFoundError(
        f"Missing Piper voice model for character={cid} language={lang}. Tried: "
        + ", ".join(str(x) for x in candidates)
    )


def synthesize_tts(job: dict, episode_id: str) -> None:
    model = resolve_voice_model(job)
    out = ROOT / "output" / episode_id / job["output"]
    out.parent.mkdir(parents=True, exist_ok=True)
    run([
        os.getenv("PIPER_BIN", "piper"),
        "--model", str(model),
        "--output_file", str(out),
    ], job["text"])


def lipsync(job: dict, episode_id: str) -> None:
    rhubarb = os.getenv("RHUBARB_BIN", "rhubarb")
    wav = ROOT / "output" / episode_id / job["output"]
    json_out = wav.with_suffix(".mouth.json")
    run([rhubarb, "-f", "json", "-o", str(json_out), str(wav)])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("episode_id")
    ap.add_argument("--language", default=None)
    ap.add_argument("--jobs", default=None, help="Optional explicit jobs json path")
    args = ap.parse_args()

    if args.jobs:
        jobs_path = Path(args.jobs)
    elif args.language:
        jobs_path = ROOT / "output" / args.episode_id / f"jobs_{args.language}.json"
    else:
        jobs_path = ROOT / "output" / args.episode_id / "jobs.json"

    jobs = json.loads(jobs_path.read_text(encoding="utf-8"))
    for job in jobs.get("tts", []):
        synthesize_tts(job, args.episode_id)
        lipsync(job, args.episode_id)

    print(json.dumps({
        "ok": True,
        "episode_id": args.episode_id,
        "language": args.language or "master",
        "tts_jobs": len(jobs.get("tts", [])),
        "next": "render",
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
