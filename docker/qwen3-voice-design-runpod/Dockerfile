FROM pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime

ARG QWEN3_TTS_COMMIT=022e286b98fbec7e1e916cb940cdf532cd9f488e

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/opt/hf-cache \
    HUGGINGFACE_HUB_CACHE=/opt/hf-cache/hub \
    HF_HUB_DISABLE_TELEMETRY=1 \
    QWEN3_TTS_MODEL_ID=Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign \
    QWEN3_TTS_MAX_TEXT_CHARS=600 \
    QWEN3_TTS_MAX_INSTRUCT_CHARS=1200

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
      git \
      libsndfile1 \
      ffmpeg \
      sox \
      ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install "runpod>=1.7,<2" \
    && python -m pip install "git+https://github.com/QwenLM/Qwen3-TTS.git@\${QWEN3_TTS_COMMIT}"

RUN python - <<'PY'
from huggingface_hub import snapshot_download

snapshot_download(
    repo_id="Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
    repo_type="model",
)
snapshot_download(
    repo_id="Qwen/Qwen3-TTS-Tokenizer-12Hz",
    repo_type="model",
)
PY

COPY handler.py /app/handler.py

RUN python -m py_compile /app/handler.py

CMD ["python", "-u", "/app/handler.py"]
