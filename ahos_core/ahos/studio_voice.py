"""Seslendirme hattı: metni WAV'a çevirir, bölüm sesini tek parça yapar.

Motor seçimi (tek adam kararı), kalite sırasıyla:
- `edge`: Microsoft Edge'in nöral sesleri (edge-tts). Türkçe dahil çok dil,
  0 $, anahtar yok; ağ gerekir. Karakter başına farklı ses verilebilir.
- `piper`: yerel nöral TTS; `.onnx` ses modeli gerektirir (indirme gerekir).
- `sapi`: Windows'ta hazır gelen motor; ağ gerekmez ama Türkçe ses yoksa
  aksan bozuktur (kapı bunu `language_match` ile raporlar).

Bu modül yalnızca seçilen motoru sürer; motor yoksa açık hata verir.
"""

from __future__ import annotations

import array
import asyncio
import json
import shutil
import subprocess
import sys
import wave
from dataclasses import dataclass
from pathlib import Path

SAMPLE_RATE = 22050

#: Edge nöral sesleri: dil -> cinsiyet -> ses kimliği
EDGE_VOICES = {
    "tr": {"female": "tr-TR-EmelNeural", "male": "tr-TR-AhmetNeural"},
    "en": {"female": "en-US-AriaNeural", "male": "en-US-GuyNeural"},
    "de": {"female": "de-DE-KatjaNeural", "male": "de-DE-ConradNeural"},
}

#: Karakter -> cinsiyet (ses ataması için)
CHARACTER_GENDER = {"aden": "female", "kaan": "male", "anne": "female", "baba": "male"}


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


def amplitude_envelope(path: str | Path, *, fps: int, total_frames: int,
                       window: float = 0.05) -> list[float]:
    """Sesin kare başına genliği (0-1). Dudak senkronu bunu kullanır.

    Her video karesi için, o kareye denk gelen ses penceresinin RMS'i alınır ve
    dosyanın en yüksek RMS'ine göre normalize edilir. Sessizlikte 0 döner.
    """

    with wave.open(str(path), "rb") as handle:
        rate = handle.getframerate() or SAMPLE_RATE
        frames = array.array("h")
        frames.frombytes(handle.readframes(handle.getnframes()))
    if not frames or total_frames <= 0:
        return [0.0] * max(0, total_frames)

    samples_per_frame = rate / float(fps)
    span = max(1, int(samples_per_frame * window * fps) if window else int(samples_per_frame))
    raw: list[float] = []
    for index in range(total_frames):
        start = int(index * samples_per_frame)
        chunk = frames[start:start + span]
        if not chunk:
            raw.append(0.0)
            continue
        total = 0.0
        for value in chunk[:: max(1, len(chunk) // 256)]:
            total += float(value) * float(value)
        raw.append((total / max(1, len(chunk[:: max(1, len(chunk) // 256)]))) ** 0.5)

    peak = max(raw) if raw else 0.0
    if peak <= 0:
        return [0.0] * total_frames
    return [min(1.0, value / peak) for value in raw]


def piper_model_path() -> Path | None:
    """Yerel piper ses modeli (varsa). `AHOS_PIPER_VOICE` ile de verilebilir."""

    import os

    configured = os.environ.get("AHOS_PIPER_VOICE", "").strip()
    if configured:
        candidate = Path(configured)
        return candidate if candidate.is_file() else None
    for folder in (Path("C:/ahos-models/piper"), Path.home() / "piper-voices"):
        if folder.is_dir():
            models = sorted(folder.glob("*.onnx"))
            if models:
                return models[0]
    return None


def synthesize_piper(text: str, out_path: str | Path, model: Path) -> Path:
    """Yerel piper (nöral TTS) ile sentez; model yoksa açık hata."""

    import os

    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    command = [sys.executable, "-m", "piper", "--model", str(model), "--output_file", str(target)]
    result = subprocess.run(command, input=text, capture_output=True, text=True,
                            timeout=300, env=env)
    if result.returncode != 0 or not target.is_file():
        raise RuntimeError("piper hatası: " + (result.stderr or "")[-200:])
    return target


def edge_voice(language: str, speaker: str = "") -> str | None:
    """Karaktere ve dile uygun Edge nöral sesini seç."""

    prefix = (language or "tr").split("-")[0].lower()
    table = EDGE_VOICES.get(prefix)
    if not table:
        return None
    gender = CHARACTER_GENDER.get((speaker or "").lower(), "female")
    return table.get(gender) or table.get("female")


def synthesize_edge(text: str, out_path: str | Path, voice: str,
                    *, rate: str = "+0%") -> Path:
    """edge-tts ile MP3 üret; ffmpeg ile 22050 Hz mono WAV'a çevir."""

    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    mp3 = target.with_suffix(".mp3")

    try:
        import edge_tts
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("edge-tts kurulu değil: " + type(exc).__name__)

    async def _run() -> None:
        communicate = edge_tts.Communicate(text, voice, rate=rate)
        await communicate.save(str(mp3))

    try:
        asyncio.run(_run())
    except Exception as exc:  # noqa: BLE001 - ağ/kota hatası açıkça söylenir
        raise RuntimeError("edge-tts hatası: " + type(exc).__name__ + ": " + str(exc)[:120])

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg bulunamadı (MP3 → WAV)")
    result = subprocess.run(
        [ffmpeg, "-y", "-loglevel", "error", "-i", str(mp3),
         "-ac", "1", "-ar", str(SAMPLE_RATE), str(target)],
        capture_output=True, text=True, timeout=120,
    )
    mp3.unlink(missing_ok=True)
    if result.returncode != 0 or not target.is_file():
        raise RuntimeError("MP3 → WAV başarısız: " + (result.stderr or "")[-200:])
    return target


def engine_for(language: str) -> str:
    """Kullanılabilir en iyi motoru seç (açıkça istenmişse ona uy)."""

    import os

    forced = os.environ.get("AHOS_VOICE_ENGINE", "").strip().lower()
    if forced in {"edge", "piper", "sapi"}:
        return forced
    prefix = (language or "tr").split("-")[0].lower()
    if prefix in EDGE_VOICES:
        return "edge"
    if piper_model_path() is not None:
        return "piper"
    return "sapi"


def synthesize(text: str, out_path: str | Path, *, language: str = "tr",
               speaker: str = "", engine: str | None = None) -> dict:
    """Metni sese çevir; kullanılan motoru ve sesi raporla."""

    chosen = engine or engine_for(language)
    target = Path(out_path).with_suffix(".wav")

    if chosen == "edge":
        voice = edge_voice(language, speaker)
        if voice is None:
            raise RuntimeError(f"edge için ses yok: {language}")
        path = synthesize_edge(text, target, voice)
        return {"engine": "edge", "voice": voice, "path": str(path),
                "language_match": True, "seconds": round(wav_duration(path), 2)}

    if chosen == "piper":
        model = piper_model_path()
        if model is None:
            raise RuntimeError("piper ses modeli yok (AHOS_PIPER_VOICE)")
        path = synthesize_piper(text, target, model)
        return {"engine": "piper", "voice": model.stem, "path": str(path),
                "language_match": language.lower() in model.name.lower(),
                "seconds": round(wav_duration(path), 2)}

    voice = pick_voice(language)
    path = synthesize_wav(text, target, voice=voice)
    return {"engine": "sapi", "voice": voice.name if voice else None,
            "culture": voice.culture if voice else None,
            "path": str(path),
            "language_match": bool(voice and voice.culture.lower().startswith(language.lower())),
            "seconds": round(wav_duration(path), 2)}


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
