from __future__ import annotations

import base64
import io
import os
from threading import Lock
from typing import Any

import numpy as np
import runpod
import soundfile as sf
import torch
from qwen_tts import Qwen3TTSModel


MODEL_ID = os.getenv(
    "QWEN3_TTS_MODEL_ID",
    "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
)
_MODEL: Qwen3TTSModel | None = None
_MODEL_LOCK = Lock()
_ALLOWED_LANGUAGES = {
    "Chinese",
    "English",
    "Japanese",
    "Korean",
    "German",
    "French",
    "Russian",
    "Portuguese",
    "Spanish",
    "Italian",
}
_MAX_TEXT_CHARS = int(os.getenv("QWEN3_TTS_MAX_TEXT_CHARS", "600"))
_MAX_INSTRUCT_CHARS = int(os.getenv("QWEN3_TTS_MAX_INSTRUCT_CHARS", "1200"))


def _load_model() -> Qwen3TTSModel:
    global _MODEL
    if _MODEL is not None:
        return _MODEL

    with _MODEL_LOCK:
        if _MODEL is None:
            if not torch.cuda.is_available():
                raise RuntimeError("CUDA GPU is required for the VoiceDesign worker")
            _MODEL = Qwen3TTSModel.from_pretrained(
                MODEL_ID,
                device_map="cuda:0",
                dtype=torch.bfloat16,
                attn_implementation="sdpa",
            )
    return _MODEL


def _wav_to_base64(wav: np.ndarray, sample_rate: int) -> tuple[str, int]:
    audio = np.asarray(wav, dtype=np.float32).reshape(-1)
    audio = np.nan_to_num(audio, nan=0.0, posinf=1.0, neginf=-1.0)
    audio = np.clip(audio, -1.0, 1.0)

    buffer = io.BytesIO()
    sf.write(buffer, audio, int(sample_rate), format="WAV", subtype="PCM_16")
    raw = buffer.getvalue()
    return base64.b64encode(raw).decode("ascii"), len(raw)


def _handle_design(data: dict[str, Any]) -> dict[str, Any]:
    text = str(data.get("text", "")).strip()
    language = str(data.get("language", "English")).strip()
    instruct = str(data.get("instruct", "")).strip()
    candidate_id = str(data.get("candidate_id", "")).strip()
    seed = int(data.get("seed", 0))
    max_new_tokens = int(data.get("max_new_tokens", 1024))

    if not text:
        raise ValueError("text is required")
    if len(text) > _MAX_TEXT_CHARS:
        raise ValueError(f"text exceeds QWEN3_TTS_MAX_TEXT_CHARS={_MAX_TEXT_CHARS}")
    if not instruct:
        raise ValueError("instruct is required")
    if len(instruct) > _MAX_INSTRUCT_CHARS:
        raise ValueError(
            f"instruct exceeds QWEN3_TTS_MAX_INSTRUCT_CHARS={_MAX_INSTRUCT_CHARS}"
        )
    if language not in _ALLOWED_LANGUAGES:
        raise ValueError(
            f"unsupported VoiceDesign language={language!r}; "
            f"supported={','.join(sorted(_ALLOWED_LANGUAGES))}"
        )
    if not candidate_id:
        raise ValueError("candidate_id is required for provenance")
    if seed < 0 or seed > 2_147_483_647:
        raise ValueError("seed must be between 0 and 2147483647")
    if max_new_tokens < 128 or max_new_tokens > 2048:
        raise ValueError("max_new_tokens must be between 128 and 2048")

    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

    model = _load_model()
    wavs, sample_rate = model.generate_voice_design(
        text=text,
        language=language,
        instruct=instruct,
        max_new_tokens=max_new_tokens,
    )
    if not wavs:
        raise RuntimeError("VoiceDesign returned no waveform")

    audio_base64, audio_bytes = _wav_to_base64(wavs[0], sample_rate)
    return {
        "ok": True,
        "provider": "qwen3-tts-voice-design-1.7b",
        "model": MODEL_ID,
        "candidate_id": candidate_id,
        "language": language,
        "seed": seed,
        "format": "wav",
        "sample_rate_hz": int(sample_rate),
        "audio_bytes": int(audio_bytes),
        "audio_base64": audio_base64,
        "synthetic_voice": True,
        "canonical_binding_created": False,
    }


def handler(job: dict[str, Any]) -> dict[str, Any]:
    data = job.get("input") or {}
    if not isinstance(data, dict):
        raise ValueError("job.input must be an object")

    if data.get("ping") is True:
        return {
            "ok": True,
            "provider": "qwen3-tts-voice-design-1.7b",
            "model_loaded": _MODEL is not None,
            "cuda_available": bool(torch.cuda.is_available()),
            "model": MODEL_ID,
            "supported_languages": sorted(_ALLOWED_LANGUAGES),
        }

    return _handle_design(data)


if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
