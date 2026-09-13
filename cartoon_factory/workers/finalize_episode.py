from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(args: list[str]) -> None:
    subprocess.run(args, check=True)


def make_scene_audio(scene_id: str, episode_dir: Path, duration: float, language: str | None) -> Path:
    audio_root = episode_dir / "audio"
    voice_dir = audio_root / language if language else audio_root
    music = audio_root / f"{scene_id}_music.wav"
    voices = sorted(voice_dir.glob(f"{scene_id}_*_*.wav"))
    mix_dir = audio_root / language if language else audio_root
    mix_dir.mkdir(parents=True, exist_ok=True)
    out = mix_dir / f"{scene_id}_mix.wav"

    if not music.exists() and not voices:
        run([
            os.getenv("FFMPEG_BIN", "ffmpeg"), "-y", "-f", "lavfi", "-i",
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
    cursor = 250
    for v in voices:
        inputs += ["-i", str(v)]
        label = f"v{idx}"
        labels.append(f"[{idx}:a]adelay={cursor}|{cursor},volume=1.0[{label}]")
        voice_labels.append(f"[{label}]")
        cursor += 2100
        idx += 1

    mix_inputs = ("[m]" if music.exists() else "") + "".join(voice_labels)
    n = (1 if music.exists() else 0) + len(voice_labels)
    labels.append(f"{mix_inputs}amix=inputs={max(n,1)}:duration=longest:normalize=0,alimiter=limit=0.95[aout]")

    run([
        os.getenv("FFMPEG_BIN", "ffmpeg"), "-y", *inputs,
        "-filter_complex", ";".join(labels),
        "-map", "[aout]",
        "-t", str(duration),
        str(out)
    ])
    return out


def mux_scene(video: Path, audio: Path, out: Path) -> None:
    run([
        os.getenv("FFMPEG_BIN", "ffmpeg"), "-y", "-i", str(video), "-i", str(audio),
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-shortest", str(out)
    ])


def main() -> None:
    episode_id = os.environ.get("EPISODE_ID", "episode_001")
    language = os.environ.get("LANGUAGE") or None
    episode_dir = ROOT / "output" / episode_id
    episode_path = episode_dir / (f"episode_{language}.json" if language else "episode.json")
    episode = json.loads(episode_path.read_text(encoding="utf-8"))

    final_scene_dir = episode_dir / "muxed" / language if language else episode_dir / "muxed"
    final_scene_dir.mkdir(parents=True, exist_ok=True)
    video_dir = episode_dir / "video" / language if language else episode_dir / "video"

    muxed: list[Path] = []
    for scene in episode.get("scenes", []):
        sid = str(scene["id"])
        video = video_dir / f"{sid}.mp4"
        if not video.exists():
            continue
        audio = make_scene_audio(sid, episode_dir, float(scene.get("duration_seconds", 8)), language)
        out = final_scene_dir / f"{sid}.mp4"
        mux_scene(video, audio, out)
        muxed.append(out)

    if not muxed:
        raise RuntimeError(f"No rendered scenes found for language={language or 'master'}")

    concat = episode_dir / (f"concat_{language}.txt" if language else "concat.txt")
    concat.write_text("\n".join(f"file '{p.resolve().as_posix()}'" for p in muxed), encoding="utf-8")
    suffix = f"_{language}" if language else ""
    final = episode_dir / f"{episode_id}{suffix}.mp4"
    run([
        os.getenv("FFMPEG_BIN", "ffmpeg"), "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat), "-c", "copy", str(final)
    ])
    print(json.dumps({
        "ok": True,
        "language": language or "master",
        "final": str(final),
        "scenes": len(muxed),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
