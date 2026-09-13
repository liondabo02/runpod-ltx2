from __future__ import annotations

import argparse
import json
from pathlib import Path

from orchestrator.main import ROOT


def build_language_jobs(episode: dict, lang: str) -> dict:
    jobs = {"tts": [], "render": [], "music": [], "qc": []}
    for scene in episode.get("scenes", []):
        sid = str(scene["id"])
        for idx, line in enumerate(scene.get("dialogue", [])):
            jobs["tts"].append({
                "job_id": f"{lang}-{sid}-voice-{idx}",
                "scene_id": sid,
                "language": lang,
                "character_id": line["character_id"],
                "text": line["text"],
                "emotion": line.get("emotion", "neutral"),
                "output": f"audio/{lang}/{sid}_{idx}_{line['character_id']}.wav",
            })
        jobs["render"].append({
            "job_id": f"{lang}-{sid}-render",
            "scene_id": sid,
            "language": lang,
            "mode": scene.get("render_mode", "sprite"),
            "scene": scene,
            "output": f"video/{lang}/{sid}.mp4",
        })
    jobs["qc"].append({
        "job_id": f"{lang}-episode-qc",
        "checks": ["duration", "missing_audio", "missing_scene", "character_ids", "peak_audio"],
    })
    return jobs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("episode_id")
    ap.add_argument("language")
    args = ap.parse_args()
    episode_dir = ROOT / "output" / args.episode_id
    ep_path = episode_dir / f"episode_{args.language}.json"
    episode = json.loads(ep_path.read_text(encoding="utf-8"))
    jobs = build_language_jobs(episode, args.language)
    out = episode_dir / f"jobs_{args.language}.json"
    out.write_text(json.dumps(jobs, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "language": args.language, "jobs": str(out)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
