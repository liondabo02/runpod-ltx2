from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def ffmpeg_run(args: list[str]) -> None:
    subprocess.run(["ffmpeg", "-y", *args], check=True)


def render_scene(scene: dict[str, Any], episode_dir: Path) -> Path:
    sid = str(scene["id"])
    duration = float(scene.get("duration_seconds", 8))
    width = int(os.getenv("CARTOON_WIDTH", "1920"))
    height = int(os.getenv("CARTOON_HEIGHT", "1080"))
    fps = int(os.getenv("CARTOON_FPS", "24"))
    out = episode_dir / "video" / f"{sid}.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)

    bg = ROOT / "assets" / "backgrounds" / f"{scene.get('location','default')}.png"
    if bg.exists():
        inputs = ["-loop", "1", "-i", str(bg)]
        vf = f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},fps={fps}"
        ffmpeg_run([*inputs, "-t", str(duration), "-vf", vf, "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out)])
    else:
        color = os.getenv("CARTOON_FALLBACK_BG", "#87CEEB")
        ffmpeg_run([
            "-f", "lavfi", "-i", f"color=c={color}:s={width}x{height}:r={fps}",
            "-t", str(duration), "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out)
        ])
    return out


def main() -> None:
    episode_json = Path(os.environ.get("EPISODE_JSON", ROOT / "output" / "episode_001" / "episode.json"))
    episode = json.loads(episode_json.read_text(encoding="utf-8"))
    episode_dir = episode_json.parent
    rendered = []
    skipped = []
    for scene in episode.get("scenes", []):
        if scene.get("render_mode", "sprite") != "sprite":
            skipped.append(scene["id"])
            continue
        rendered.append(str(render_scene(scene, episode_dir)))
    manifest = {"rendered": rendered, "gpu_special_skipped": skipped}
    (episode_dir / "render_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, **manifest}, ensure_ascii=False))


if __name__ == "__main__":
    main()
