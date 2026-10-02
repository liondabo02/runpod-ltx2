from __future__ import annotations

import base64
import io
import os
import tempfile
import wave
from pathlib import Path
from threading import Lock
from typing import Any

import numpy as np
import runpod
import torch
from chatterbox.mtl_tts import ChatterboxMultilingualTTS, SUPPORTED_LANGUAGES


_MODEL: ChatterboxMultilingualTTS | None = None
_MODEL_LOCK = Lock()
_MAX_TEXT_CHARS = int(os.getenv("CHATTERBOX_MAX_TEXT_CHARS", "1200"))


def _load_model() -> ChatterboxMultilingualTTS:
    global _MODEL
    if _MODEL is not None:
        return _MODEL

    with _MODEL_LOCK:
        if _MODEL is None:
            if not torch.cuda.is_available():
                raise RuntimeError("CUDA GPU is required for this RunPod worker")
            _MODEL = ChatterboxMultilingualTTS.from_pretrained(
                device="cuda",
                t3_model="v3",
            )
    return _MODEL


def _decode_reference_wav(audio_base64: str) -> Path:
    try:
        raw = base64.b64decode(audio_base64, validate=True)
    except Exception as exc:
        raise ValueError("reference_audio_base64 is not valid base64") from exc

    if len(raw) < 44:
        raise ValueError("reference audio is too small to be a WAV")
    if raw[:4] != b"RIFF" or raw[8:12] != b"WAVE":
        raise ValueError("reference audio must be a RIFF/WAVE file")

    handle = tempfile.NamedTemporaryFile(
        prefix="ahos-chatterbox-ref-",
        suffix=".wav",
        delete=False,
    )
    try:
        handle.write(raw)
        handle.flush()
    finally:
        handle.close()
    return Path(handle.name)


def _tensor_to_wav_bytes(wav_tensor: torch.Tensor, sample_rate: int) -> bytes:
    audio = wav_tensor.detach().cpu().float().numpy()
    audio = np.asarray(audio).reshape(-1)
    audio = np.nan_to_num(audio, nan=0.0, posinf=1.0, neginf=-1.0)
    audio = np.clip(audio, -1.0, 1.0)
    pcm16 = (audio * 32767.0).astype("<i2")

    out = io.BytesIO()
    with wave.open(out, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(int(sample_rate))
        wav_file.writeframes(pcm16.tobytes())
    return out.getvalue()


def _float_input(
    data: dict[str, Any],
    key: str,
    default: float,
    *,
    minimum: float,
    maximum: float,
) -> float:
    value = float(data.get(key, default))
    if value < minimum or value > maximum:
        raise ValueError(f"{key} must be between {minimum} and {maximum}")
    return value


def _handle_tts(data: dict[str, Any]) -> dict[str, Any]:
    text = str(data.get("text", "")).strip()
    language_id = str(data.get("language_id", "")).strip().lower()
    voice_id = str(data.get("voice_id", "")).strip()
    reference_audio_base64 = data.get("reference_audio_base64")
    allow_builtin_voice = bool(data.get("allow_builtin_voice", False))

    if not text:
        raise ValueError("text is required")
    if len(text) > _MAX_TEXT_CHARS:
        raise ValueError(
            f"text exceeds CHATTERBOX_MAX_TEXT_CHARS={_MAX_TEXT_CHARS}; "
            "split long dialogue before synthesis"
        )
    if language_id not in SUPPORTED_LANGUAGES:
        raise ValueError(
            f"unsupported language_id={language_id!r}; "
            f"supported={','.join(sorted(SUPPORTED_LANGUAGES))}"
        )
    if not voice_id:
        raise ValueError("voice_id is required for AHOS voice provenance")
    if not reference_audio_base64 and not allow_builtin_voice:
        raise ValueError(
            "reference_audio_base64 is required for character-consistent voice "
            "synthesis; set allow_builtin_voice=true only for an explicit smoke test"
        )

    exaggeration = _float_input(
        data,
        "exaggeration",
        0.5,
        minimum=0.0,
        maximum=2.0,
    )
    cfg_weight = _float_input(
        data,
        "cfg_weight",
        0.5,
        minimum=0.0,
        maximum=1.5,
    )
    temperature = _float_input(
        data,
        "temperature",
        0.8,
        minimum=0.05,
        maximum=2.0,
    )

    model = _load_model()
    reference_path: Path | None = None
    try:
        if reference_audio_base64:
            reference_path = _decode_reference_wav(str(reference_audio_base64))

        generated = model.generate(
            text=text,
            language_id=language_id,
            audio_prompt_path=(
                str(reference_path) if reference_path is not None else None
            ),
            exaggeration=exaggeration,
            cfg_weight=cfg_weight,
            temperature=temperature,
        )
        wav_bytes = _tensor_to_wav_bytes(generated, model.sr)
    finally:
        if reference_path is not None:
            reference_path.unlink(missing_ok=True)

    return {
        "ok": True,
        "provider": "chatterbox-multilingual-v3",
        "voice_id": voice_id,
        "language_id": language_id,
        "format": "wav",
        "sample_rate_hz": int(model.sr),
        "audio_base64": base64.b64encode(wav_bytes).decode("ascii"),
        "audio_bytes": len(wav_bytes),
        "watermarked": True,
        "model": "Chatterbox Multilingual V3",
    }


def handler(job: dict[str, Any]) -> dict[str, Any]:
    data = job.get("input") or {}
    if not isinstance(data, dict):
        raise ValueError("job.input must be an object")

    if data.get("ping") is True:
        return {
            "ok": True,
            "provider": "chatterbox-multilingual-v3",
            "model_loaded": _MODEL is not None,
            "cuda_available": bool(torch.cuda.is_available()),
            "supported_languages": sorted(SUPPORTED_LANGUAGES),
        }

    return _handle_tts(data)


if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
