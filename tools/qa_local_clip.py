"""Yerel Aden klini için ffprobe + kare farkı QA raporu."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from PIL import Image

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

JOB = Path(__file__).resolve().parents[1] / "studio" / "jobs" / "aden-clip"
VIDEO = JOB / "aden_idle_5s.mp4"


def probe() -> dict:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=codec_type,width,height,r_frame_rate,nb_frames",
         "-show_entries", "format=duration,size", "-of", "json", str(VIDEO)],
        capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def motion(frames_dir: Path) -> float:
    files = sorted(frames_dir.glob("f*.png"))
    if len(files) < 2:
        return 0.0
    a = Image.open(files[0]).convert("L").resize((96, 64))
    b = Image.open(files[len(files) // 2]).convert("L").resize((96, 64))
    diff = sum(abs(x - y) for x, y in zip(a.getdata(), b.getdata()))
    return round(diff / (a.width * a.height) / 255.0, 5)


def main() -> int:
    data = probe()
    stream = next(item for item in data["streams"] if item["codec_type"] == "video")
    duration = round(float(data["format"]["duration"]), 3)
    fps = stream["r_frame_rate"]
    checks = {
        "duration_5s": abs(duration - 5.0) <= 0.05,
        "resolution_768x512": (stream["width"], stream["height"]) == (768, 512),
        "fps_24": fps == "24/1",
        "frames_120": int(stream["nb_frames"]) == 120,
        "real_motion": motion(JOB / "frames") > 0.001,
        "file_nonempty": VIDEO.stat().st_size > 100_000,
    }
    report = {"schema": "ahos.local-clip.qa.v1", "video": str(VIDEO),
              "duration": duration, "fps": fps,
              "resolution": [stream["width"], stream["height"]],
              "frames": int(stream["nb_frames"]), "bytes": VIDEO.stat().st_size,
              "identity_status": "PENDING_IDENTITY_REVIEW",
              "audio": "silent (voice/lipsync ayrı aşama)",
              "checks": checks, "passed": all(checks.values())}
    (JOB / "qa.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                                 encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
