from __future__ import annotations

import base64
import os
import tempfile
from pathlib import Path
from threading import Lock
from typing import Any

import runpod
import torch
from openvoice import se_extractor
from openvoice.api import ToneColorConverter


CHECKPOINT_DIR = Path(os.getenv(
    "OPENVOICE_CHECKPOINT_DIR", "/opt/openvoice/checkpoints_v2/converter"
))
_CONVERTER: ToneColorConverter | None = None
_LOCK = Lock()
_MAX_AUDIO_BYTES = int(os.getenv("OPENVOICE_MAX_AUDIO_BYTES", str(20 * 1024 * 1024)))


def _converter() -> ToneColorConverter:
    global _CONVERTER
    if _CONVERTER is not None:
        return _CONVERTER
    with _LOCK:
        if _CONVERTER is None:
            device = "cuda:0" if torch.cuda.is_available() else "cpu"
            model = ToneColorConverter(
                str(CHECKPOINT_DIR / "config.json"),
                device=device,
                enable_watermark=False,
            )
            model.load_ckpt(str(CHECKPOINT_DIR / "checkpoint.pth"))
            _CONVERTER = model
    return _CONVERTER


def _decode_wav(value: object, label: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} is required")
    try:
        raw = base64.b64decode(value, validate=True)
    except Exception as exc:
        raise ValueError(f"{label} is invalid base64") from exc
    if len(raw) < 44 or len(raw) > _MAX_AUDIO_BYTES:
        raise ValueError(f"{label} size is outside policy")
    if raw[:4] != b"RIFF" or raw[8:12] != b"WAVE":
        raise ValueError(f"{label} must be RIFF/WAVE")
    return raw


def _convert(data: dict[str, Any]) -> dict[str, Any]:
    if data.get("operation") != "tone_color_convert":
        raise ValueError("operation must be tone_color_convert")
    if data.get("language") != "ku-latn":
        raise ValueError("worker is restricted to ku-latn identity transfer")
    if data.get("preserve_source_linguistics") is not True:
        raise ValueError("preserve_source_linguistics must be true")
    character_id = str(data.get("character_id") or "").strip()
    if not character_id or len(character_id) > 128:
        raise ValueError("character_id is required")
    tau = float(data.get("tau", 0.3))
    if not 0.0 <= tau <= 1.0:
        raise ValueError("tau must be between 0 and 1")
    source = _decode_wav(data.get("source_audio_base64"), "source_audio_base64")
    target = _decode_wav(
        data.get("target_reference_audio_base64"), "target_reference_audio_base64"
    )

    with tempfile.TemporaryDirectory(prefix="ahos-openvoice-") as directory:
        root = Path(directory)
        source_path, target_path, output_path = (
            root / "source.wav", root / "target.wav", root / "output.wav"
        )
        source_path.write_bytes(source)
        target_path.write_bytes(target)
        converter = _converter()
        source_se, _ = se_extractor.get_se(str(source_path), converter, vad=True)
        target_se, _ = se_extractor.get_se(str(target_path), converter, vad=True)
        converter.convert(
            audio_src_path=str(source_path), src_se=source_se, tgt_se=target_se,
            output_path=str(output_path), message="@MyShell", tau=tau,
        )
        output = output_path.read_bytes()
    if len(output) < 44 or output[:4] != b"RIFF" or output[8:12] != b"WAVE":
        raise RuntimeError("OpenVoice produced invalid WAV")
    return {
        "ok": True,
        "provider": "openvoice-v2-tone-transfer",
        "character_id": character_id,
        "language": "ku-latn",
        "identity_transfer": True,
        "source_linguistics_preserved": True,
        "text_regenerated": False,
        "audio_base64": base64.b64encode(output).decode("ascii"),
        "audio_bytes": len(output),
    }


def handler(job: dict[str, Any]) -> dict[str, Any]:
    data = job.get("input") or {}
    if not isinstance(data, dict):
        raise ValueError("job.input must be an object")
    if data.get("ping") is True:
        return {
            "ok": True,
            "provider": "openvoice-v2-tone-transfer",
            "cuda_available": bool(torch.cuda.is_available()),
            "model_loaded": _CONVERTER is not None,
            "operation": "tone_color_convert",
        }
    return _convert(data)


if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
