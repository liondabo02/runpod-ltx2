"""Aden referans dosyalarının salt-okunur teknik kaydı (orijinaller değiştirilmez)."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2")
OUT = Path(__file__).resolve().parents[1] / "studio" / "qa" / "aden-reference-manifest.json"
FILES = [
    ROOT / "deliverables" / "S01-PARK-KITE-001" / "keyframes" / "keyframe-girl-seed-77.png",
    ROOT / "deliverables" / "S01-PARK-KITE-001" / "park-kite-take2-girl-1080p.mp4",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def video_spec(path: Path) -> dict:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height,r_frame_rate,codec_name,nb_frames,duration", "-of", "json", str(path)],
        capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return {"ffprobe_error": result.stderr.strip()[:200]}
    payload = json.loads(result.stdout)
    stream = (payload.get("streams") or [{}])[0]
    return {"width": stream.get("width"), "height": stream.get("height"),
            "fps": stream.get("r_frame_rate"), "codec": stream.get("codec_name"),
            "frames": stream.get("nb_frames"), "duration_seconds": stream.get("duration")}


rows = []
for path in FILES:
    row = {"path": str(path), "relative": str(path.relative_to(ROOT)), "exists": path.is_file()}
    if path.is_file():
        row.update({"bytes": path.stat().st_size, "sha256": sha256(path)})
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
            with Image.open(path) as image:
                row.update({"width": image.width, "height": image.height, "format": image.format})
        else:
            row.update({"video": video_spec(path)})
    rows.append(row)

payload = {
    "schema": "ahos.studio.aden-reference.v1",
    "generated_at": "2026-11-08",
    "originals_modified": False,
    "note": "Salt-okunur kayıt; görsel üretilmedi, yüz değiştirilmedi.",
    "files": rows,
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(payload, ensure_ascii=False))
