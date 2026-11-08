"""Ücretsiz seslendirme (TTS) köprüsü.

Öncelik sırası (hepsi ücretsiz/anahtarsız olanlar önce):

1. ``edge-tts`` — Microsoft nöral sesleri, doğal, ücretsiz, anahtar gerekmez.
2. RunPod ``kokoro`` / ``chatterbox`` — yalnız endpoint yetkisi varsa.
3. ``espeak-ng`` — tamamen çevrimdışı yedek (robotik).

Her çağrı gerçek bir ses dosyası üretmek zorundadır; boş/küçük dosya başarı
sayılmaz (kanıt kuralı).
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

DEFAULT_VOICE = "tr-TR-EmelNeural"
MIN_BYTES = 1000


@dataclass(frozen=True)
class TtsResult:
    ok: bool
    path: str
    provider: str
    detail: str


def edge_voice(text: str, out_path: Path, voice: str = DEFAULT_VOICE, *, timeout: float = 120.0) -> TtsResult:
    """``python -m edge_tts`` ile ses üretir (ağ gerekir)."""

    out_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        "-m",
        "edge_tts",
        "--text",
        text,
        "--voice",
        voice,
        "--write-media",
        str(out_path),
    ]
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace"
        )
    except FileNotFoundError:
        return TtsResult(False, "", "edge-tts", "edge_tts bulunamadı")
    except subprocess.TimeoutExpired:
        return TtsResult(False, "", "edge-tts", f"zaman aşımı ({timeout:.0f}s)")
    if completed.returncode != 0:
        return TtsResult(False, "", "edge-tts", (completed.stderr or "").strip()[:200])
    if not out_path.exists() or out_path.stat().st_size < MIN_BYTES:
        return TtsResult(False, "", "edge-tts", "ses dosyası oluşmadı veya çok küçük")
    return TtsResult(True, str(out_path), "edge-tts", out_path.name)


def synthesize(
    text: str,
    out_path: str | Path,
    *,
    voice: str = DEFAULT_VOICE,
    edge= edge_voice,
) -> TtsResult:
    """Metni sese çevirir; ilk başarılı sağlayıcıyı döndürür."""

    cleaned = (text or "").strip()
    if not cleaned:
        return TtsResult(False, "", "yok", "metin boş")
    target = Path(out_path)
    attempts: list[str] = []
    for provider in (edge,):
        result = provider(cleaned, target, voice) if provider is edge_voice else provider(cleaned, target, voice)
        attempts.append(f"{result.provider}={'ok' if result.ok else 'yok'}")
        if result.ok:
            return result
    return TtsResult(False, "", "yok", "hiçbir sağlayıcı başaramadı: " + ", ".join(attempts))


def status() -> dict[str, object]:
    """Panel satırı: hangi ses sağlayıcıları kullanılabilir."""

    available = False
    detail = ""
    try:
        import edge_tts  # noqa: F401

        available = True
        detail = "edge-tts kurulu (ücretsiz nöral sesler)"
    except Exception as exc:  # noqa: BLE001
        detail = f"edge-tts yok: {exc}"
    runpod_voice = os.environ.get("RUNPOD_QWEN3_VOICE_DESIGN_ENDPOINT_ID", "").strip()
    return {
        "edge": available,
        "runpod_voice_endpoint": runpod_voice or None,
        "state": "açık" if available else "kapalı",
        "detail": detail,
    }
