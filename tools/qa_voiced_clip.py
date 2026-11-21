"""Sesli Aden klini QA: stream, süre, ses enerjisi ve viseme ağız hareketi."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
JOB = Path(__file__).resolve().parents[1] / "studio" / "jobs" / "aden-clip"
VIDEO = JOB / "aden_idle_5s_voiced.mp4"
FRAMES = JOB / "voiced-frames"


def probe(path: Path) -> dict:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=codec_type,width,height,r_frame_rate,nb_frames,sample_rate,channels",
         "-show_entries", "format=duration,size", "-of", "json", str(path)],
        capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def audio_rms(path: Path) -> float:
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "audio.wav"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(path),
                        "-ac", "1", "-ar", "22050", str(wav)], check=True)
        with wave.open(str(wav), "rb") as handle:
            data = np.frombuffer(handle.readframes(handle.getnframes()), dtype="<i2")
        return float(np.sqrt(np.mean(data.astype(np.float64) ** 2))) if len(data) else 0.0


def mouth_delta(a: Path, b: Path) -> float:
    with Image.open(a) as ia, Image.open(b) as ib:
        pa = np.asarray(ia.convert("L"), dtype=np.float64)
        pb = np.asarray(ib.convert("L"), dtype=np.float64)
    return float(np.mean(np.abs(pa - pb)))


def main() -> int:
    data = probe(VIDEO)
    video = next((s for s in data["streams"] if s["codec_type"] == "video"), {})
    audio = next((s for s in data["streams"] if s["codec_type"] == "audio"), None)
    duration = round(float(data["format"]["duration"]), 3)
    files = sorted(FRAMES.glob("f*.png"))
    checks = {
        "video_768x512": (video.get("width"), video.get("height")) == (768, 512),
        "fps_24": video.get("r_frame_rate") == "24/1",
        "frames_120": int(video.get("nb_frames", 0)) == 120,
        "audio_stream": audio is not None,
        "audio_mono_22k": bool(audio) and int(audio.get("channels", 0)) == 1,
        "duration_5s": abs(duration - 5.0) <= 0.15,
        "audio_not_silent": audio is not None and audio_rms(VIDEO) > 50,
        "viseme_mouth_moves": len(files) > 30 and mouth_delta(files[5], files[21]) > 0.5,
        "file_nonempty": VIDEO.stat().st_size > 100_000,
    }
    report = {
        "schema": "ahos.voiced-clip.qa.v1",
        "video": str(VIDEO), "duration": duration,
        "video_stream": video, "audio_stream": audio,
        "audio_rms": round(audio_rms(VIDEO), 2),
        "mouth_delta": round(mouth_delta(files[5], files[21]), 3) if len(files) > 30 else 0.0,
        "identity_status": "PENDING_IDENTITY_REVIEW",
        "voice_status": "TEMPORARY_ADULT_EDGE_TTS / NOT FINAL",
        "checks": checks, "passed": all(checks.values()),
    }
    (JOB / "qa_voiced.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
