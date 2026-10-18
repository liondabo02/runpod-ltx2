FROM pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime

ARG CHATTERBOX_COMMIT=5de7a54aa4e5e2baadb0182dde554908b48b85c2

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/opt/hf-cache \
    HUGGINGFACE_HUB_CACHE=/opt/hf-cache/hub \
    CHATTERBOX_MAX_TEXT_CHARS=1200

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
      git \
      libsndfile1 \
      ffmpeg \
      ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install "runpod>=1.7,<2" \
    && python -m pip install "git+https://github.com/resemble-ai/chatterbox.git@${CHATTERBOX_COMMIT}"

# Bake only the official multilingual V3 inference assets into the image so
# RunPod cold starts do not need to download model weights at request time.
RUN python - <<'PY'
from huggingface_hub import snapshot_download

snapshot_download(
    repo_id="ResembleAI/chatterbox",
    repo_type="model",
    revision="main",
    allow_patterns=[
        "ve.pt",
        "t3_mtl23ls_v3.safetensors",
        "s3gen.pt",
        "grapheme_mtl_merged_expanded_v1.json",
        "conds.pt",
        "Cangjie5_TC.json",
    ],
)
PY

COPY handler.py /app/handler.py

RUN python -m py_compile /app/handler.py

CMD ["python", "-u", "/app/handler.py"]
