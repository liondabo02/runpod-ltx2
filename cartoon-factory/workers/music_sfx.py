from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def ensure_silence(path: Path, seconds: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i",
        "anullsrc=channel_layout=stereo:sample_rate=48000",
        "-t", str(max(seconds, 0.1)), str(path)
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def build_audio_plan(scene: dict[str, Any]) -> dict[str, Any]:
    sid = str(scene["id"])
    duration = float(scene.get("duration_seconds", 8))
    mood = scene.get("music_mood", "light playful")
    sfx = scene.get("sfx", [])
    return {
        "scene_id": sid,
        "duration_seconds": duration,
        "music": {
            "mood": mood,
            "strategy": os.getenv("MUSIC_STRATEGY", "library_or_generate"),
            "duck_under_dialogue_db": -10,
            "fade_in_ms": 250,
            "fade_out_ms": 500,
        },
        "sfx": [{"name": name, "gain_db": -6} for name in sfx],
    }


def main() -> None:
    jobs_path = Path(os.environ.get("JOBS_JSON", ROOT / "output" / "episode_001" / "jobs.json"))
    episode_dir = jobs_path.parent
    jobs = json.loads(jobs_path.read_text(encoding="utf-8"))
    plans = []
    for job in jobs.get("music", []):
        scene = {
            "id": job["scene_id"],
            "duration_seconds": job.get("duration_seconds", 8),
            "music_mood": job.get("mood", "light playful"),
            "sfx": job.get("sfx", []),
        }
        plans.append(build_audio_plan(scene))
        fallback = episode_dir / job["output"]
        if not fallback.exists():
            ensure_silence(fallback, float(job.get("duration_seconds", 8)))
    out = episode_dir / "audio_plan.json"
    out.write_text(json.dumps(plans, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "audio_plan": str(out), "scenes": len(plans)}))


if __name__ == "__main__":
    main()
