from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(args: list[str]) -> None:
    subprocess.run(args, check=True)


def make_scene_audio(scene_id: str, episode_dir: Path, duration: float) -> Path:
    audio_dir = episode_dir / "audio"
    music = audio_dir / f"{scene_id}_music.wav"
    voices = sorted(audio_dir.glob(f"{scene_id}_*_*.wav"))
    out = audio_dir / f"{scene_id}_mix.wav"

    if not music.exists() and not voices:
        run([
            "ffmpeg", "-y", "-f", "lavfi", "-i",
            "anullsrc=channel_layout=stereo:sample_rate=48000",
            "-t", str(duration), str(out)
        ])
        return out

    inputs: list[str] = []
    labels: list[str] = []
    idx = 0
    if music.exists():
        inputs += ["-i", str(music)]
        labels.append(f"[{idx}:a]volume=0.25[m]")
        idx += 1

    voice_labels: list[str] = []
    delay_ms = 300
    cursor = 250
    for v in voices:
        inputs += ["-i", str(v)]
        label = f"v{idx}"
        labels.append(f"[{idx}:a]adelay={cursor}|{cursor},volume=1.0[{label}]")
        voice_labels.append(f"[{label}]")
        cursor += delay_ms + 1800
        idx += 1

    mix_inputs = ("[m]" if music.exists() else "") + "".join(voice_labels)
    n = (1 if music.exists() else 0) + len(voice_labels)
    labels.append(f"{mix_inputs}amix=inputs={max(n,1)}:duration=longest:normalize=0,alimiter=limit=0.95[aout]")

    run([
        "ffmpeg", "-y", *inputs,
        "-filter_complex", ";".join(labels),
        "-map", "[aout]",
        "-t", str(duration),
        str(out)
    ])
    return out


def mux_scene(video: Path, audio: Path, out: Path) -> None:
    run([
        "ffmpeg", "-y", "-i", str(video), "-i", str(audio),
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-shortest", str(out)
    ])


def main() -> None:
    episode_id = os.environ.get("EPISODE_ID", "episode_001")
    episode_dir = ROOT / "output" / episode_id
    episode = json.loads((episode_dir / "episode.json").read_text(encoding="utf-8"))
    final_scene_dir = episode_dir / "muxed"
    final_scene_dir.mkdir(parents=True, exist_ok=True)

    muxed: list[Path] = []
    for scene in episode.get("scenes", []):
        sid = str(scene["id"])
        video = episode_dir / "video" / f"{sid}.mp4"
        if not video.exists():
            continue
        audio = make_scene_audio(sid, episode_dir, float(scene.get("duration_seconds", 8)))
        out = final_scene_dir / f"{sid}.mp4"
        mux_scene(video, audio, out)
        muxed.append(out)

    if not muxed:
        raise RuntimeError("No rendered scenes found")

    concat = episode_dir / "concat.txt"
    concat.write_text("\n".join(f"file '{p.resolve().as_posix()}'" for p in muxed), encoding="utf-8")
    final = episode_dir / f"{episode_id}.mp4"
    run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat), "-c", "copy", str(final)
    ])
    print(json.dumps({"ok": True, "final": str(final), "scenes": len(muxed)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
