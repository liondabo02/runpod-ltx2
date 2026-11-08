"""S01E001 ses envanteri: mevcut tr.wav referansları + bölüm replikleri.

Salt okunur; ses dosyalarını değiştirmez. Çıktı: JSON + Markdown.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import wave
from collections import Counter
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def probe(path: Path) -> dict:
    with wave.open(str(path), "rb") as handle:
        channels, rate, frames, width = (handle.getnchannels(), handle.getframerate(),
                                         handle.getnframes(), handle.getsampwidth())
        raw = handle.readframes(frames)
    data = np.frombuffer(raw, dtype=np.int16).astype(float)
    rms = float(np.sqrt((data ** 2).mean()) / 32768) if data.size else 0.0
    return {"exists": True, "duration_seconds": round(frames / rate, 2),
            "sample_rate": rate, "channels": channels, "sample_width": width,
            "dbfs": round(20 * math.log10(rms), 1) if rms > 0 else -120.0,
            "bytes": path.stat().st_size, "sha256": sha256(path)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episode", default="studio/s01e001/episode.json")
    parser.add_argument("--audio", default=r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2"
                                        r"\control_plane_v2\runtime\private\animation-studio\audio\core-voices")
    parser.add_argument("--out", default="studio/s01e001/voice-inventory.json")
    args = parser.parse_args(argv)

    episode = json.loads(Path(args.episode).read_text(encoding="utf-8"))
    counts: Counter[str] = Counter()
    for scene in episode.get("scenes") or []:
        for line in scene.get("dialogue") or []:
            counts[line["speaker"]] += 1

    audio = Path(args.audio)
    assets = []
    for character in ("aden", "kaan", "esra", "harun"):
        path = audio / character / "tr.wav"
        record = {"character_id": character, "path": str(path), "role": "reference voice print"}
        record.update(probe(path) if path.is_file() else {"exists": False})
        record["episode_lines"] = counts.get(character, 0)
        assets.append(record)

    payload = {
        "schema": "ahos.voice-inventory.v1",
        "episode_id": "S01E001",
        "measured_with": "wave + numpy RMS; dosyalar değiştirilmedi",
        "assets": assets,
        "episode_line_counts": dict(counts),
        "usable": [item["character_id"] for item in assets if item["exists"]],
        "missing_episode_lines": [item["character_id"] for item in assets if item["exists"]],
        "quality_risks": [
            "Tüm referanslar 24 kHz mono; yayın standardı 48 kHz değil.",
            "Dosyalar bölüm repliği değil, jenerik referans kaydı; duygu/ton çeşitliliği yok.",
            "Çocuk yaşında ses doğallığı ve Türkçe fonem kapsaması insan dinlemesiyle doğrulanmadı.",
            "Robotiklik değerlendirmesi yapılmadı; bu nedenle hiçbir ses 'onaylı' değil.",
            "fatos/tr.wav süre aykırısı bu bölüm kadrosunda değil; yine de genel katalog riski."
        ],
        "approval": "NOT_EVALUATED",
        "note": "Referans sesler kullanılabilir ses izi olarak listelenir; bölüm replikleri henüz seslendirilmedi.",
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["# S01E001 ses envanteri", "",
             "Ölçüm: `wave` + RMS; dosyalar değiştirilmedi. Onay durumu: **NOT_EVALUATED**.", "",
             "| Karakter | Dosya | Süre | SR | Kanallar | dBFS | Bölüm repliği |",
             "|---|---|---|---|---|---|---|"]
    for item in assets:
        lines.append(f"| {item['character_id']} | {'var' if item['exists'] else 'YOK'} | "
                     f"{item.get('duration_seconds', '-')} | {item.get('sample_rate', '-')} | "
                     f"{item.get('channels', '-')} | {item.get('dbfs', '-')} | {item['episode_lines']} |")
    lines += ["", "## Kullanılabilir", "",
              ", ".join(payload["usable"]) or "yok", "",
              "## Eksik", "",
              "Bölüm repliklerinin tamamı seslendirilmedi; mevcut dosyalar jenerik referanstır.", "",
              "## Kalite riskleri", ""] + [f"- {risk}" for risk in payload["quality_risks"]]
    Path("studio/s01e001/SES-ENVANTERI.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"assets": len(assets), "usable": payload["usable"],
                      "lines": dict(counts), "out": str(out)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
