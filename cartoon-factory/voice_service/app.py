from __future__ import annotations

import io
import os
from functools import lru_cache
from pathlib import Path

import torch
import torchaudio as ta
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from chatterbox.mtl_tts import ChatterboxMultilingualTTS

app = FastAPI(title="Cartoon Factory Voice Service", version="0.1.0")
VOICE_REFS = Path(os.getenv("VOICE_REFERENCE_DIR", "/voices"))
DEVICE = os.getenv("CHATTERBOX_DEVICE", "cuda" if torch.cuda.is_available() else "cpu")


class SpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=800)
    language: str
    character_id: str
    exaggeration: float = 0.45
    cfg_weight: float = 0.35


@lru_cache(maxsize=1)
def model() -> ChatterboxMultilingualTTS:
    return ChatterboxMultilingualTTS.from_pretrained(device=DEVICE, t3_model="v3")


@app.get("/health")
def health() -> dict:
    return {"ok": True, "device": DEVICE, "engine": "chatterbox-multilingual-v3"}


@app.post("/v1/speech")
def speech(req: SpeechRequest) -> Response:
    ref = VOICE_REFS / f"{req.character_id}.wav"
    kwargs = {
        "language_id": req.language,
        "exaggeration": req.exaggeration,
        "cfg_weight": req.cfg_weight,
    }
    if ref.exists():
        kwargs["audio_prompt_path"] = str(ref)
    try:
        wav = model().generate(req.text, **kwargs)
        buf = io.BytesIO()
        ta.save(buf, wav.cpu(), model().sr, format="wav")
        return Response(content=buf.getvalue(), media_type="audio/wav")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
