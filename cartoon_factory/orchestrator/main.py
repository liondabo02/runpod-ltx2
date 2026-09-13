from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import httpx
import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def load_series() -> dict[str, Any]:
    with open(ROOT / "config" / "series.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def llm_chat(messages: list[dict[str, str]], temperature: float = 0.7) -> str:
    base = os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")
    key = os.getenv("LLM_API_KEY", "")
    model = os.getenv("LLM_MODEL", "openrouter/free")
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    payload = {"model": model, "messages": messages, "temperature": temperature}
    with httpx.Client(timeout=180) as client:
        r = client.post(f"{base}/chat/completions", headers=headers, json=payload)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


def extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        raise ValueError("LLM did not return JSON")
    return json.loads(text[start : end + 1])


def make_episode(idea: str) -> dict[str, Any]:
    cfg = load_series()
    series = cfg["series"]
    characters = cfg["characters"]
    char_summary = [
        {"id": c["id"], "name": c["name"], "role": c["role"], "personality": c["personality"]}
        for c in characters
    ]
    system = f"""You are the head writer and production planner of a recurring 2D children's cartoon.
Return ONLY valid JSON. Language: {series['language']}. Target age: {series['target_age']}.
Episode length: about {series['episode_minutes']} minutes. Use ONLY registered recurring characters.
Characters: {json.dumps(char_summary, ensure_ascii=False)}
Rules: {json.dumps(series['rules'], ensure_ascii=False)}
Create a complete episode with title, lesson, logline and scene list.
Each scene must include: id, duration_seconds, location, background_prompt, characters, action,
dialogue (array of {{character_id,text,emotion}}), music_mood, sfx (array), camera, render_mode.
render_mode must be 'sprite' for normal shots and 'gpu_special' only when generative video is truly useful.
Aim for roughly {cfg['production']['scene_count_target']} scenes and total duration near {series['episode_minutes']*60} seconds.
"""
    user = f"Episode idea: {idea}\nWrite the full production-ready scene manifest."
    raw = llm_chat([
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ], float(cfg["production"].get("llm_temperature", 0.7)))
    episode = extract_json(raw)
    episode["series_title"] = series["title"]
    episode["source_idea"] = idea
    return episode


def build_jobs(episode: dict[str, Any]) -> dict[str, Any]:
    jobs: dict[str, Any] = {"tts": [], "render": [], "music": [], "qc": []}
    for scene in episode.get("scenes", []):
        sid = scene["id"]
        for idx, line in enumerate(scene.get("dialogue", [])):
            jobs["tts"].append({
                "job_id": f"{sid}-voice-{idx}",
                "scene_id": sid,
                "character_id": line["character_id"],
                "text": line["text"],
                "emotion": line.get("emotion", "neutral"),
                "output": f"audio/{sid}_{idx}_{line['character_id']}.wav",
            })
        jobs["music"].append({
            "job_id": f"{sid}-music",
            "scene_id": sid,
            "mood": scene.get("music_mood", "light playful"),
            "duration_seconds": scene.get("duration_seconds", 8),
            "output": f"audio/{sid}_music.wav",
        })
        jobs["render"].append({
            "job_id": f"{sid}-render",
            "scene_id": sid,
            "mode": scene.get("render_mode", "sprite"),
            "scene": scene,
            "output": f"video/{sid}.mp4",
        })
    jobs["qc"].append({"job_id": "episode-qc", "checks": [
        "duration", "missing_audio", "missing_scene", "character_ids", "black_frames", "peak_audio"
    ]})
    return jobs


def main() -> None:
    ap = argparse.ArgumentParser(description="Cartoon Factory episode planner")
    ap.add_argument("idea", help="Episode idea in natural language")
    ap.add_argument("--episode-id", default="episode_001")
    args = ap.parse_args()

    out = ROOT / "output" / args.episode_id
    out.mkdir(parents=True, exist_ok=True)
    episode = make_episode(args.idea)
    jobs = build_jobs(episode)
    (out / "episode.json").write_text(json.dumps(episode, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "jobs.json").write_text(json.dumps(jobs, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "episode_dir": str(out), "scenes": len(episode.get('scenes', []))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
