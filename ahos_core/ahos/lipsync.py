"""Rhubarb Lip Sync adaptörü: gerçek WAV -> viseme zaman çizelgesi.

Harici ikili dosya repo dışında tutulur; yolu `AHOS_RHUBARB_EXE` veya
`tools/rhubarb.cmd` üzerinden gelir. Binary yoksa sahte viseme üretilmez.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RHUBARB = Path(
    r"C:\actions-runner\_work\tools\rhubarb\Rhubarb-Lip-Sync-1.14.0-Windows\rhubarb.exe"
)


class RhubarbError(RuntimeError):
    pass


def rhubarb_executable() -> Path | None:
    """Env, PATH veya bilinen yerel kurulumdan Rhubarb'ı bul."""

    configured = os.getenv("AHOS_RHUBARB_EXE", "").strip()
    candidates = [
        Path(configured) if configured else None,
        DEFAULT_RHUBARB,
        ROOT / "tools" / "rhubarb.cmd",
        Path(shutil.which("rhubarb.exe") or ""),
    ]
    for candidate in candidates:
        if candidate and candidate.is_file():
            return candidate
    return None


def parse_rhubarb(payload: dict, *, source: str = "") -> dict:
    """Rhubarb JSON'unu doğrula; boş/ters zaman çizelgesini reddet."""

    if not isinstance(payload, dict):
        raise RhubarbError("Rhubarb çıktısı nesne değil")
    cues = payload.get("mouthCues")
    if not isinstance(cues, list) or not cues:
        raise RhubarbError("Rhubarb mouthCues boş")
    parsed: list[dict] = []
    previous_end = -1.0
    for cue in cues:
        if not isinstance(cue, dict):
            raise RhubarbError("geçersiz mouth cue")
        try:
            start = float(cue["start"])
            end = float(cue["end"])
        except (KeyError, TypeError, ValueError) as exc:
            raise RhubarbError("mouth cue zamanı geçersiz") from exc
        value = str(cue.get("value") or "").strip()
        if not value or end <= start or start < previous_end - 1e-6:
            raise RhubarbError("mouth cue sırası/zamanı geçersiz")
        parsed.append({"start": round(start, 3), "end": round(end, 3), "value": value})
        previous_end = end
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    duration = metadata.get("duration")
    if duration is not None:
        try:
            if float(duration) < parsed[-1]["end"] - 0.05:
                raise RhubarbError("viseme süresi metadata ile uyuşmuyor")
        except (TypeError, ValueError) as exc:
            raise RhubarbError("metadata.duration geçersiz") from exc
    return {
        "schema": "ahos.lipsync.rhubarb.v1",
        "source": source or metadata.get("soundFile") or "",
        "duration": round(float(duration), 3) if duration is not None else parsed[-1]["end"],
        "visemes": parsed,
    }


def generate_visemes(wav_path: str | Path, out_json: str | Path, *,
                     executable: str | Path | None = None,
                     timeout: float = 120.0) -> dict:
    """Gerçek WAV'ı Rhubarb ile işleyip viseme JSON'u üret."""

    wav = Path(wav_path)
    if not wav.is_file() or wav.stat().st_size < 100:
        raise RhubarbError(f"WAV yok/çok küçük: {wav}")
    if wav.read_bytes()[:4] != b"RIFF":
        raise RhubarbError(f"WAV RIFF imzası yok: {wav}")
    exe = Path(executable) if executable else rhubarb_executable()
    if exe is None or not exe.is_file():
        raise RhubarbError("Rhubarb bulunamadı; AHOS_RHUBARB_EXE ayarla")
    out = Path(out_json)
    out.parent.mkdir(parents=True, exist_ok=True)
    command = [str(exe), "-f", "json", "-o", str(out), "--machineReadable", str(wav)]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RhubarbError(f"Rhubarb çalıştırılamadı: {type(exc).__name__}") from exc
    if result.returncode != 0:
        raise RhubarbError(f"Rhubarb exit={result.returncode}: {(result.stderr or '')[-300:]}")
    if not out.is_file():
        raise RhubarbError("Rhubarb çıktı dosyası yazmadı")
    try:
        payload = json.loads(out.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RhubarbError("Rhubarb JSON okunamadı") from exc
    return parse_rhubarb(payload, source=str(wav))


def load_visemes(path: str | Path) -> dict:
    return parse_rhubarb(json.loads(Path(path).read_text(encoding="utf-8")), source=str(path))


def viseme_at(visemes: list[dict], seconds: float) -> str:
    """Verilen anda geçerli viseme; dışındaysa sessiz 'X'."""

    for cue in visemes:
        if float(cue["start"]) <= seconds < float(cue["end"]):
            return str(cue["value"])
    return "X"
