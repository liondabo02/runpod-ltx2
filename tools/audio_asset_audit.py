"""Ses varlığı denetimi — mevcut sesleri **silmez**, yeniden üretmez.

Her karakter klasörü için `reference-en.wav` ve `tr.wav` dosyalarını ölçer:
süre, örnekleme hızı, kanal, RMS (dBFS). Sessiz/aşırı kısa/eksik dosyaları
işaretler. Medine ve Ramin bebek olduğu için ayrı ele alınır (bilgi notu).

Rapor varsayılan olarak private dizine yazılır; public repoya kişisel ses yolu
veya aile verisi girmez.

Kullanım:
    python tools/audio_asset_audit.py
    python tools/audio_asset_audit.py --verbose --report <path>
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import wave
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUDIO = (ROOT / "control_plane_v2" / "runtime" / "private"
                 / "animation-studio" / "audio" / "core-voices")
DEFAULT_REPORT = (ROOT / "control_plane_v2" / "runtime" / "private"
                  / "animation-studio" / "audio-audit.local.json")
BABIES = {"medine", "ramin"}
FILES = ("reference-en.wav", "tr.wav")


def probe_wav(path: Path) -> dict:
    with wave.open(str(path), "rb") as handle:
        channels = handle.getnchannels()
        width = handle.getsampwidth()
        rate = handle.getframerate()
        frames = handle.getnframes()
        raw = handle.readframes(frames)
    dtype = {1: np.uint8, 2: np.int16, 4: np.int32}.get(width)
    if dtype is None:
        raise ValueError(f"unsupported sample width: {width}")
    data = np.frombuffer(raw, dtype=dtype).astype(np.float64)
    if dtype is np.uint8:
        data = (data - 128.0) * 256.0
    scale = float(2 ** (8 * width - 1))
    rms = float(np.sqrt(np.square(data).mean()) / scale) if data.size else 0.0
    dbfs = 20.0 * math.log10(rms) if rms > 1e-9 else -120.0
    return {"duration": round(frames / rate, 3) if rate else 0.0,
            "sample_rate": rate, "channels": channels,
            "dbfs": round(dbfs, 1), "bytes": path.stat().st_size}


def audit(root: Path = DEFAULT_AUDIO) -> dict:
    characters: list[dict] = []
    if not root.is_dir():
        return {"root": str(root), "exists": False, "characters": [],
                "summary": {"folders": 0, "files": 0, "issues": 0}}
    for folder in sorted(path for path in root.iterdir() if path.is_dir()):
        character_id = folder.name
        entry: dict = {"character_id": character_id, "files": {}, "issues": []}
        for name in FILES:
            path = folder / name
            if not path.is_file():
                entry["files"][name] = {"exists": False}
                entry["issues"].append(f"missing:{name}")
                continue
            try:
                info = probe_wav(path)
            except (wave.Error, ValueError, OSError) as exc:
                entry["files"][name] = {"exists": True, "error": type(exc).__name__}
                entry["issues"].append(f"unreadable:{name}")
                continue
            info["exists"] = True
            entry["files"][name] = info
            if info["duration"] < 0.4:
                entry["issues"].append(f"too_short:{name}")
            if info["dbfs"] <= -50.0:
                entry["issues"].append(f"silent:{name}")
        rates = [item.get("sample_rate") for item in entry["files"].values()
                 if isinstance(item, dict) and item.get("sample_rate")]
        if len(set(rates)) > 1:
            entry["issues"].append("sample_rate_mismatch")
        if character_id in BABIES:
            entry["note"] = "baby: yalnız bebek ses davranışı beklenir"
        characters.append(entry)

    # Süre aykırısı: aynı dosya türünde medyanın 3 katından uzun (yanlış take işareti).
    for name in FILES:
        durations = sorted(item["files"].get(name, {}).get("duration")
                           for item in characters
                           if item["files"].get(name, {}).get("duration"))
        if len(durations) >= 5:
            median = durations[len(durations) // 2]
            for entry in characters:
                duration = entry["files"].get(name, {}).get("duration")
                if duration and median and duration > 3 * median:
                    entry["issues"].append(f"duration_outlier:{name}")

    files = sum(len([n for n in entry["files"] if entry["files"][n].get("exists")])
                for entry in characters)
    issues = sum(len(entry["issues"]) for entry in characters)
    return {"root": str(root), "exists": True, "characters": characters,
            "summary": {"folders": len(characters), "files": files,
                        "issues": issues,
                        "characters_with_issues": sum(1 for e in characters if e["issues"])}}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ses varlığı denetimi (salt okunur)")
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    report = audit()
    target = Path(args.report)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.verbose:
        for entry in report["characters"]:
            lengths = {name: item.get("duration") for name, item in entry["files"].items()}
            print(entry["character_id"], lengths, entry["issues"])
    print(json.dumps({"report": str(target), **report["summary"]}, ensure_ascii=False))
    return 0 if report["exists"] and report["summary"]["issues"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
