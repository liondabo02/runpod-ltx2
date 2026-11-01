"""Seslendirme hattı: metni WAV'a çevirir, bölüm sesini tek parça yapar.

Motor seçimi (tek adam kararı):
- `sapi`: Windows'ta hazır gelen konuşma motoru. Ağ gerekmez, 0 $.
  Kurulu ses(ler) hangi dilde ise onu kullanır; Türkçe ses yoksa bu bir
  KALİTE notudur (kapı bunu ayrıca raporlar).
- `piper`: yerel nöral TTS; `.onnx` ses modeli gerektirir (indirme gerekir).
- `runpod`: Kokoro/Chatterbox; API anahtarı gerektirir.

Bu modül ağ çağrısı yapmaz; yalnızca yerel motoru sürer.
"""

from __future__ import annotations

import array
import json
import shutil
import subprocess
import sys
import wave
from dataclasses import dataclass
from pathlib import Path

SAMPLE_RATE = 22050


@dataclass(frozen=True, slots=True)
class Voice:
    name: str
    culture: str
    gender: str = ""


def _powershell() -> str | None:
    return shutil.which("powershell") or shutil.which("pwsh")


def list_voices() -> list[Voice]:
    """Kurulu SAPI sesleri (ağ yok)."""

    shell = _powershell()
    if not shell:
        return []
    script = (
        "Add-Type -AssemblyName System.Speech;"
        "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
        "$s.GetInstalledVoices() | ForEach-Object {"
        "  $v=$_.VoiceInfo;"
        "  Write-Output ($v.Name + '|' + $v.Culture.Name + '|' + $v.Gender)"
        "}"
    )
    result = subprocess.run([shell, "-NoProfile", "-Command", script],
                            capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        return []
    voices = []
    for line in (result.stdout or "").splitlines():
        parts = [p.strip() for p in line.strip().split("|")]
        if len(parts) >= 2 and parts[0]:
            voices.append(Voice(parts[0], parts[1], parts[2] if len(parts) > 2 else ""))
    return voices


def pick_voice(language: str = "tr", voices: list[Voice] | None = None) -> Voice | None:
    """Dile en yakın sesi seç; tam eşleşme yoksa ilk sesi döndür (not düşülür)."""

    voices = list_voices() if voices is None else voices
    if not voices:
        return None
    prefix = (language or "").split("-")[0].lower()
    for voice in voices:
        if voice.culture.lower().startswith(prefix):
            return voice
    return voices[0]


def synthesize_wav(text: str, out_path: str | Path, *, voice: Voice | None = None,
                   rate: int = 0, volume: int = 100) -> Path:
    """SAPI ile tek repliği WAV'a yaz."""

    shell = _powershell()
    if not shell:
        raise RuntimeError("PowerShell bulunamadı; SAPI kullanılamıyor")
    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    voice_line = f"$s.SelectVoice('{voice.name}');" if voice is not None else ""
    script = (
        "Add-Type -AssemblyName System.Speech;"
        "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
        f"{voice_line}"
        f"$s.Rate={int(rate)};$s.Volume={int(volume)};"
        f"$s.SetOutputToWaveFile('{target}');"
        f"$s.Speak({json.dumps(text, ensure_ascii=False)});"
        "$s.Dispose();"
    )
    result = subprocess.run([shell, "-NoProfile", "-Command", script],
                            capture_output=True, text=True, timeout=180)
    if result.returncode != 0 or not target.is_file():
        raise RuntimeError("SAPI hatası: " + (result.stderr or "")[-200:])
    return target


def wav_duration(path: str | Path) -> float:
    with wave.open(str(path), "rb") as handle:
        return handle.getnframes() / float(handle.getframerate() or SAMPLE_RATE)


def build_track(clips: list[tuple[Path, float, float]], total_seconds: float,
                out_path: str | Path, *, sample_rate: int = SAMPLE_RATE) -> Path:
    """(dosya, başlangıç, süre) listesini tek sessiz/konuşmalı WAV'a diz."""

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    total_frames = int(total_seconds * sample_rate)
    buffer = array.array("h", [0]) * max(1, total_frames)

    for path, start, duration in clips:
        with wave.open(str(path), "rb") as handle:
            rate = handle.getframerate() or sample_rate
            if rate != sample_rate or handle.getnchannels() != 1 or handle.getsampwidth() != 2:
                raise ValueError(f"desteklenmeyen WAV biçimi: {path}")
            frames = array.array("h")
            frames.frombytes(handle.readframes(handle.getnframes()))
        offset = int(start * sample_rate)
        limit = min(len(frames), max(0, total_frames - offset))
        for index in range(limit):
            buffer[offset + index] = frames[index]

    with wave.open(str(out), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(buffer.tobytes())
    return out


def rms(path: str | Path) -> float:
    with wave.open(str(path), "rb") as handle:
        frames = array.array("h")
        frames.frombytes(handle.readframes(handle.getnframes()))
    if not frames:
        return 0.0
    total = 0
    for value in frames[:: max(1, len(frames) // 4000)]:
        total += float(value) * float(value)
    count = max(1, len(frames[:: max(1, len(frames) // 4000)]))
    return (total / count) ** 0.5


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="seslendirme hattı")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--text", default=None)
    parser.add_argument("--out", default=None)
    parser.add_argument("--language", default="tr")
    args = parser.parse_args(argv)

    if args.list:
        print(json.dumps([v.__dict__ for v in list_voices()], ensure_ascii=False))
        return 0
    if not args.text or not args.out:
        parser.error("--text ve --out gerekli")
    voice = pick_voice(args.language)
    path = synthesize_wav(args.text, args.out, voice=voice)
    print(json.dumps({"path": str(path), "voice": voice.name if voice else None,
                      "culture": voice.culture if voice else None,
                      "seconds": round(wav_duration(path), 2),
                      "rms": round(rms(path), 1)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
