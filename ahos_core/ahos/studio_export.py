"""Bölümü düzenlenebilir formatlara aktarır (kurgu programları için).

Neden: üretilen video tek başına yeterli değil; bir insan kurgucu (DaVinci
Resolve, Kdenlive, Premiere) sahneleri kesmek, süre değiştirmek veya müzik
eklemek isteyebilir. Bu modül standart, açık formatlar üretir:

- **CMX3600 EDL**: hemen hemen her kurgu programının içe aktardığı kesme listesi.
- **CSV çekim listesi**: sahne, konuşmacı, metin, başlangıç/bitiş (Excel/Sheets).
- **storyboard.json**: kendi basit şemamız (sahne + replik + süre).

Bunlar tersine mühendislik değil, kamuya açık standartlardır; hiçbir üçüncü
taraf hizmetin kodu veya çıktısı kopyalanmaz.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

FPS = 24


def _tc(seconds: float, fps: int = FPS) -> str:
    frames = int(round(seconds * fps))
    h, frames = divmod(frames, 3600 * fps)
    m, frames = divmod(frames, 60 * fps)
    s, frames = divmod(frames, fps)
    return f"{h:02d}:{m:02d}:{s:02d}:{frames:02d}"


def export_edl(manifest: dict, out_path: str | Path, *, title: str | None = None,
               fps: int = FPS) -> Path:
    """Sahne sınırlarından CMX3600 EDL üret (tek video dosyası referansı)."""

    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    name = (title or manifest.get("title") or "episode").replace("\n", " ")[:60]

    lines = [
        f"TITLE: {name}",
        "FCM: NON-DROP FRAME",
        "",
    ]
    record = 0.0
    index = 1
    for scene in manifest.get("scenes_detail") or []:
        duration = float(scene.get("seconds") or 0.0)
        if duration <= 0:
            continue
        lines.append(
            f"{index:03d}  AX       V     C        "
            f"{_tc(record, fps)} {_tc(record + duration, fps)} "
            f"{_tc(record, fps)} {_tc(record + duration, fps)}"
        )
        lines.append(f"* FROM CLIP NAME: {name} sahne {scene.get('scene_id')}")
        if scene.get("setting"):
            lines.append(f"* COMMENT: {scene['setting']}")
        record += duration
        index += 1

    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def export_shotlist(manifest: dict, timeline: list[dict], out_path: str | Path) -> Path:
    """CSV çekim listesi: sahne, konuşmacı, metin, başlangıç, bitiş."""

    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["scene", "speaker", "text", "start_seconds", "end_seconds", "duration"])
        for row in timeline:
            writer.writerow([
                row.get("scene_id", ""),
                row.get("speaker", ""),
                row.get("text", ""),
                f"{float(row.get('start', 0)):.2f}",
                f"{float(row.get('end', 0)):.2f}",
                f"{float(row.get('end', 0)) - float(row.get('start', 0)):.2f}",
            ])
    return target


def export_storyboard(manifest: dict, timeline: list[dict], out_path: str | Path) -> Path:
    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "title": manifest.get("title"),
        "duration_seconds": manifest.get("duration_seconds"),
        "fps": manifest.get("fps", FPS),
        "resolution": manifest.get("resolution"),
        "scenes": manifest.get("scenes_detail") or [],
        "lines": timeline,
    }
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return target


def export_all(manifest: dict, timeline: list[dict], out_dir: str | Path) -> dict:
    out = Path(out_dir)
    edl = export_edl(manifest, out / "episode.edl")
    csv_path = export_shotlist(manifest, timeline, out / "shotlist.csv")
    board = export_storyboard(manifest, timeline, out / "storyboard.json")
    return {"edl": str(edl), "shotlist": str(csv_path), "storyboard": str(board)}
