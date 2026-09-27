FROM pytorch/pytorch:2.2.2-cuda12.1-cudnn8-runtime

ARG OPENVOICE_COMMIT=74a1d147b17a8c3092dd5430504bd83ef6c7eb23

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    OPENVOICE_CHECKPOINT_DIR=/opt/openvoice/checkpoints_v2/converter

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential ca-certificates ffmpeg git libsndfile1 unzip wget \
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

RUN wget -q https://myshell-public-repo-host.s3.amazonaws.com/openvoice/checkpoints_v2_0417.zip \
      -O /tmp/openvoice-checkpoints.zip \
    && unzip -q /tmp/openvoice-checkpoints.zip -d /opt/openvoice \
    && test -f /opt/openvoice/checkpoints_v2/converter/config.json \
    && test -f /opt/openvoice/checkpoints_v2/converter/checkpoint.pth \
    && rm /tmp/openvoice-checkpoints.zip

COPY handler.py /app/handler.py
RUN python -m py_compile /app/handler.py \
    && python -c "from openvoice import se_extractor; from openvoice.api import ToneColorConverter"

CMD ["python", "-u", "/app/handler.py"]
