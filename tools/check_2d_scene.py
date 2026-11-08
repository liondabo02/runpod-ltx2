"""2D iskelet sahnesi teknik QA — 3D/profesyonel iddiası yok."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    video = Path(args.video)
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json",
                            str(video)], capture_output=True, text=True, check=True)
    meta = json.loads(probe.stdout)
    stream = next(item for item in meta["streams"] if item["codec_type"] == "video")
    has_audio = any(item["codec_type"] == "audio" for item in meta["streams"])

    capture = cv2.VideoCapture(str(video))
    frames = []
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
    capture.release()
    diffs = [float(np.abs(frames[i].astype(np.int16) - frames[i - 1].astype(np.int16)).mean())
             for i in range(1, len(frames))]
    blank = sum(1 for frame in frames if float(frame.std()) < 1.5)
    payload = {
        "schema": "ahos.studio.2d-rig-qa.v1",
        "status": "TECHNICAL_TEST_PENDING_REVIEW",
        "professional_quality": "NOT_ACHIEVED",
        "video": str(video),
        "sha256": hashlib.sha256(video.read_bytes()).hexdigest(),
        "bytes": video.stat().st_size,
        "codec": stream.get("codec_name"),
        "width": stream.get("width"), "height": stream.get("height"),
        "fps": stream.get("r_frame_rate"), "frames": len(frames),
        "duration_seconds": float(meta["format"]["duration"]),
        "audio": "SILENT" if not has_audio else "PRESENT",
        "is_3d": bool(manifest.get("is_3d")),
        "method": manifest.get("method"),
        "joints": manifest.get("joints"),
        "blank_frames": blank,
        "mean_motion": round(float(np.mean(diffs)), 3),
        "min_motion": round(float(np.min(diffs)), 3),
        "issues": ["identity_vector_approximation_not_owner_approved", "no_audio",
                   "no_phoneme_lipsync", "not_3d", "professional_gate_failed"],
        "note": "Gerçek eklem hareketi var; profesyonel/3D/onaylı değil.",
    }
    Path(args.out).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: payload[key] for key in ("status", "frames", "duration_seconds", "fps",
                                                    "mean_motion", "blank_frames", "sha256")},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
