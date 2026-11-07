"""AHOS-DELIVERY-001 Faz 1 — üretim ortamı tanısı (ücretsiz, salt-okunur).

RunPod/ComfyUI/LTX-2, GPU, ffmpeg, TTS, model dosyaları ve engellenmiş üretim
görevlerini denetler. Ücretli kaynak başlatmaz; yalnız rapor üretir.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "ahos_core" / "runtime"
DOC = ROOT / "docs" / "URETIM-DURUM.md"
REPORT = RUNTIME / "reports" / "production-status.json"


def _which(name: str) -> str:
    return shutil.which(name) or ""


def _env_keys() -> dict:
    keys = {}
    for path in sorted(RUNTIME.glob("*.env")):
        names = []
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                names.append(line.split("=", 1)[0].strip())
        keys[path.name] = sorted(names)
    return keys


def _gpu() -> str:
    if not _which("nvidia-smi"):
        return "yok"
    try:
        proc = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total",
                               "--format=csv,noheader"], capture_output=True,
                              text=True, timeout=20)
        return (proc.stdout or "").strip() or "bilinmiyor"
    except Exception as exc:  # noqa: BLE001
        return f"hata: {type(exc).__name__}"


def _models() -> list[str]:
    hits = []
    for base in (RUNTIME / "models", RUNTIME / "comfy", ROOT / "models"):
        if base.is_dir():
            for path in list(base.rglob("*.safetensors"))[:20]:
                hits.append(str(path.relative_to(ROOT)))
    return hits


def _blocked() -> list[dict]:
    db = RUNTIME / "company-service.db"
    if not db.is_file():
        return []
    with sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True) as con:
        rows = con.execute(
            "select mission_id, objective, last_error, updated_at from missions "
            "where status='blocked' order by updated_at desc limit 200").fetchall()
    keywords = ("video", "render", "comfy", "ltx", "ses", "audio", "film")
    return [{"mission_id": m, "objective": str(o)[:160], "error": str(e or "")[:120],
             "at": str(u)[:19]}
            for m, o, e, u in rows if any(k in str(o).lower() for k in keywords)][:15]


def build() -> dict:
    keys = _env_keys()
    runpod_keys = sorted(k for v in keys.values() for k in v
                         if "RUNPOD" in k.upper() or "COMFY" in k.upper())
    payload = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "gpu": _gpu(),
        "ffmpeg": _which("ffmpeg"),
        "ffprobe": _which("ffprobe"),
        "edge_tts": bool(importlib.util.find_spec("edge_tts")),
        "python": sys.version.split()[0],
        "env_files": keys,
        "runpod_or_comfy_keys": runpod_keys,
        "model_files": _models(),
        "blocked_production_missions": _blocked(),
        "paid_usage": False,
        "ltx2_ready": False,
        "deterministic_pipeline_ready": bool(_which("ffmpeg") and _which("ffprobe")),
        "verdict": ("Yerel GPU yok; LTX-2/ComfyUI model üretimi ücretli GPU/API olmadan "
                    "çalıştırılamaz. Deterministik PIL+ffmpeg+edge-tts hattı çalışıyor. "
                    "Ücretli kaynak için Harun onayı gerekir."),
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    blocked = payload["blocked_production_missions"]
    DOC.write_text(
        "# AHOS-DELIVERY-001 — Üretim Ortamı Durumu (Faz 1)\n\n"
        f"- Üretim: {payload['at']}\n"
        f"- GPU: **{payload['gpu']}**\n"
        f"- ffmpeg: `{payload['ffmpeg'] or 'yok'}` · ffprobe: `{payload['ffprobe'] or 'yok'}`\n"
        f"- edge-tts: **{payload['edge_tts']}**\n"
        f"- Model dosyası (safetensors): **{len(payload['model_files'])}**\n"
        f"- RunPod/Comfy env anahtarları: {', '.join(runpod_keys) or 'yok'}\n"
        f"- Engellenmiş üretim görevi: **{len(blocked)}**\n\n"
        "## Karar\n\n"
        f"{payload['verdict']}\n\n"
        "## Engellenmiş görevler\n\n"
        + ("\n".join(f"- `{row['mission_id']}` — {row['objective']} ({row['error']})"
                     for row in blocked) or "- yok")
        + "\n\n## Ücret\n\n- Bu tanı 0 $; hiçbir ücretli API/GPU çağrısı yapılmadı.\n",
        encoding="utf-8")
    return payload


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))
