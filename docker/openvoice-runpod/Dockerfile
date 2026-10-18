FROM pytorch/pytorch:2.2.2-cuda12.1-cudnn8-runtime

ARG OPENVOICE_COMMIT=74a1d147b17a8c3092dd5430504bd83ef6c7eb23
ARG OPENVOICE_V2_REVISION=f36e7edfe1684461a8343844af60babc2efbb727

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    OPENVOICE_CHECKPOINT_DIR=/opt/openvoice/checkpoints_v2/converter

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential ca-certificates ffmpeg git libsndfile1 wget \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
COPY openvoice-worker.patch /app/openvoice-worker.patch

RUN python -m pip install --upgrade "pip<26" setuptools wheel \
    && python -m pip install --prefer-binary -r /app/requirements.txt

RUN git clone --filter=blob:none https://github.com/myshell-ai/OpenVoice.git /opt/openvoice \
    && cd /opt/openvoice \
    && git checkout "${OPENVOICE_COMMIT}" \
    && git apply /app/openvoice-worker.patch \
    && python -m pip install --no-deps -e .

RUN mkdir -p /opt/openvoice/checkpoints_v2/converter \
    && wget --quiet --tries=5 --timeout=30 \
      "https://huggingface.co/myshell-ai/OpenVoiceV2/resolve/${OPENVOICE_V2_REVISION}/converter/config.json?download=true" \
      -O /opt/openvoice/checkpoints_v2/converter/config.json \
    && wget --quiet --tries=5 --timeout=30 \
      "https://huggingface.co/myshell-ai/OpenVoiceV2/resolve/${OPENVOICE_V2_REVISION}/converter/checkpoint.pth?download=true" \
      -O /opt/openvoice/checkpoints_v2/converter/checkpoint.pth \
    && echo "9652c27e92b6b2a91632590ac9962ef7ae2b712e5c5b7f4c34ec55ee2b37ab9e  /opt/openvoice/checkpoints_v2/converter/checkpoint.pth" \
      | sha256sum --check --strict \
    && python -c "import json; p='/opt/openvoice/checkpoints_v2/converter/config.json'; d=json.load(open(p)); assert d.get('model') and d.get('data')"

COPY handler.py /app/handler.py
RUN python -m py_compile /app/handler.py \
    && python -c "from openvoice import se_extractor; from openvoice.api import ToneColorConverter"

CMD ["python", "-u", "/app/handler.py"]
