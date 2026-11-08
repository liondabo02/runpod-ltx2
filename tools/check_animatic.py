"""Animatik MP4 teknik QA: ffprobe + kare taraması + SHA-256."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import cv2

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    video = Path(args.video)
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(video)],
        capture_output=True, text=True, check=True)
    meta = json.loads(probe.stdout)
    stream = next(item for item in meta["streams"] if item["codec_type"] == "video")
    has_audio = any(item["codec_type"] == "audio" for item in meta["streams"])

    capture = cv2.VideoCapture(str(video))
    fps = capture.get(cv2.CAP_PROP_FPS) or 0
    blank = []
    frames = 0
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if float(gray.std()) < 2.0:
            blank.append(round(frames / fps, 3))
        frames += 1
    capture.release()

    payload = {
        "schema": "ahos.studio.animatic-qa.v1",
        "path": str(video),
        "sha256": hashlib.sha256(video.read_bytes()).hexdigest(),
        "bytes": video.stat().st_size,
        "codec": stream.get("codec_name"),
        "width": stream.get("width"),
        "height": stream.get("height"),
        "fps": stream.get("r_frame_rate"),
        "frames": frames,
        "duration_seconds": float(meta["format"]["duration"]),
        "audio": "SILENT" if not has_audio else "PRESENT",
        "blank_frames": len(blank),
        "blank_timestamps": blank[:12],
        "content_frames": frames - len(blank),
        "status": "VIDEO_READY" if (stream.get("width") == 1920 and stream.get("height") == 1080
                                     and stream.get("r_frame_rate") == "24/1"
                                     and abs(float(meta["format"]["duration"]) - 30.0) < 0.05
                                     and frames == 720 and not has_audio) else "FAILED",
    }
    Path(args.out).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: payload[key] for key in ("status", "frames", "duration_seconds", "fps",
                                                    "width", "height", "audio", "blank_frames", "sha256")},
                     ensure_ascii=False))
    return 0 if payload["status"] == "VIDEO_READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
