from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def ffmpeg_run(args: list[str]) -> None:
    subprocess.run([os.getenv("FFMPEG_BIN", "ffmpeg"), "-y", *args], check=True)


def slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", value.strip().lower()) or "default"


def character_id(item: Any) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        return str(item.get("id") or item.get("character_id") or item.get("name") or "")
    return ""


def choose_pose(cid: str, scene: dict[str, Any]) -> Path | None:
    action = str(scene.get("action", "idle")).lower()
    actions = ["run", "walk", "sit", "jump", "point", "wave", "talk", "idle"]
    selected = next((a for a in actions if a in action), "idle")
    base = ROOT / "assets" / "characters" / slug(cid) / "poses"
    for name in [f"{selected}_front.png", "idle_front.png"]:
        path = base / name
        if path.exists():
            return path
    return None


def render_scene(scene: dict[str, Any], episode_dir: Path, language: str | None = None) -> Path:
    sid = str(scene["id"])
    duration = float(scene.get("duration_seconds", 8))
    width = int(os.getenv("CARTOON_WIDTH", "1920"))
    height = int(os.getenv("CARTOON_HEIGHT", "1080"))
    fps = int(os.getenv("CARTOON_FPS", "24"))
    video_dir = episode_dir / "video" / language if language else episode_dir / "video"
    out = video_dir / f"{sid}.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)

    location = slug(str(scene.get("location", "default")))
    bg = ROOT / "assets" / "backgrounds" / f"{location}.png"

    args: list[str] = []
    if bg.exists():
        args += ["-loop", "1", "-i", str(bg)]
    else:
        color = os.getenv("CARTOON_FALLBACK_BG", "#87CEEB")
        args += ["-f", "lavfi", "-i", f"color=c={color}:s={width}x{height}:r={fps}"]

    sprite_paths: list[Path] = []
    for item in scene.get("characters", []):
        cid = character_id(item)
        if not cid:
            continue
        pose = choose_pose(cid, scene)
        if pose:
            sprite_paths.append(pose)
            args += ["-loop", "1", "-i", str(pose)]

    filters = [f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},fps={fps}[bg]"]
    previous = "bg"
    n = max(len(sprite_paths), 1)
    for idx, _path in enumerate(sprite_paths, start=1):
        char_h = int(height * 0.62)
        x = int((idx / (n + 1)) * width - char_h * 0.32)
        y = int(height - char_h - height * 0.05)
        filters.append(f"[{idx}:v]scale=-1:{char_h},format=rgba[s{idx}]")
        out_label = f"v{idx}"
        filters.append(f"[{previous}][s{idx}]overlay=x={x}:y={y}:format=auto[{out_label}]")
        previous = out_label

    if not sprite_paths:
        filters.append("[bg]null[vout]")
        map_label = "[vout]"
    else:
        map_label = f"[{previous}]"

    ffmpeg_run([
        *args,
        "-filter_complex", ";".join(filters),
        "-map", map_label,
        "-t", str(duration),
        "-r", str(fps),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        str(out),
    ])
    return out


def main() -> None:
    episode_json = Path(os.environ.get("EPISODE_JSON", ROOT / "output" / "episode_001" / "episode.json"))
    language = os.environ.get("LANGUAGE") or None
    episode = json.loads(episode_json.read_text(encoding="utf-8"))
    if not language:
        language = episode.get("language") if episode_json.name != "episode.json" else None
    episode_dir = episode_json.parent
    rendered = []
    skipped = []
    for scene in episode.get("scenes", []):
        if scene.get("render_mode", "sprite") != "sprite":
            skipped.append(scene["id"])
            continue
        rendered.append(str(render_scene(scene, episode_dir, language)))
    manifest = {"language": language or "master", "rendered": rendered, "gpu_special_skipped": skipped}
    manifest_name = f"render_manifest_{language}.json" if language else "render_manifest.json"
    (episode_dir / manifest_name).write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, **manifest}, ensure_ascii=False))


if __name__ == "__main__":
    main()
