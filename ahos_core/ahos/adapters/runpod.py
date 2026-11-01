"""AHOS ↔ RunPod (GPU/video) köprüsü — dosya kuyruğu.

RunPod işleri pahalı olabilir; bu yüzden varsayılan durum **kapalıdır**. Bir iş
ancak ``AHOS_RUNPOD_ENABLED=1`` ve bir uç nokta tanımlıysa kuyruğa girer.

Sözleşme (Ruflo köprüsüyle aynı kalıp):
  istek  ``runtime/runpod-queue/<job>.json``
  sonuç  ``runtime/runpod-results/<job>.json``

Worker (``ops/runpod/runpod-worker.ps1``) bu dosyaları işler. Uç nokta yoksa
sonuç ``unconfigured`` olarak yazılır — sahte başarı üretilmez.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

JOB_KINDS = {"video", "render", "image", "training"}


def queue_dir(runtime_dir: str | Path) -> Path:
    return Path(runtime_dir) / "runpod-queue"


def results_dir(runtime_dir: str | Path) -> Path:
    return Path(runtime_dir) / "runpod-results"


def _load_env_file(runtime_dir: str | Path | None) -> None:
    """``runtime/runpod.env`` varsa ortam değişkenlerine ekle (üzerine yazmadan)."""

    import os

    if runtime_dir is None:
        return
    path = Path(runtime_dir) / "runpod.env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip())


def enabled(runtime_dir: str | Path | None = None) -> bool:
    import os

    _load_env_file(runtime_dir)
    return os.environ.get("AHOS_RUNPOD_ENABLED", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def endpoint_for(kind: str, runtime_dir: str | Path | None = None) -> str:
    """İş türüne göre serverless uç noktası (env ile eşlenir)."""

    import os

    _load_env_file(runtime_dir)
    specific = os.environ.get(f"AHOS_RUNPOD_ENDPOINT_{kind.upper()}", "").strip()
    return specific or os.environ.get("AHOS_RUNPOD_ENDPOINT", "").strip()


def submit(
    runtime_dir: str | Path,
    *,
    job_id: str,
    kind: str,
    prompt: str,
    project: str,
    max_usd: float = 0.0,
) -> Path:
    if kind not in JOB_KINDS:
        raise ValueError(f"bilinmeyen iş türü: {kind}")
    if not enabled(runtime_dir):
        raise PermissionError(
            "RunPod kapalı: AHOS_RUNPOD_ENABLED=1 olmadan GPU işi gönderilmez"
        )
    if max_usd != 0:
        raise PermissionError("RunPod için bütçe 0 USD olmalı (max_usd=0)")

    endpoint = endpoint_for(kind, runtime_dir)
    if not endpoint:
        raise PermissionError(
            f"RunPod uç noktası tanımlı değil: AHOS_RUNPOD_ENDPOINT_{kind.upper()}"
        )

    target = queue_dir(runtime_dir)
    target.mkdir(parents=True, exist_ok=True)
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in job_id)[:80]
    path = target / f"{safe}.json"
    path.write_text(
        json.dumps(
            {
                "job_id": job_id,
                "kind": kind,
                "prompt": prompt,
                "project": project,
                "endpoint": endpoint,
                "max_usd": 0.0,
                "submitted_at": time.time(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def read_result(runtime_dir: str | Path, job_id: str) -> dict[str, object] | None:
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in job_id)[:80]
    path = results_dir(runtime_dir) / f"{safe}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def status(runtime_dir: str | Path) -> dict[str, object]:
    _load_env_file(runtime_dir)
    """Panel satırı için gerçek durum."""

    queued = len(list(queue_dir(runtime_dir).glob("*.json"))) if queue_dir(runtime_dir).exists() else 0
    done = len(list(results_dir(runtime_dir).glob("*.json"))) if results_dir(runtime_dir).exists() else 0
    return {
        "enabled": enabled(),
        "queued": queued,
        "results": done,
        "state": "açık" if enabled() else "kapalı (AHOS_RUNPOD_ENABLED=0)",
    }
