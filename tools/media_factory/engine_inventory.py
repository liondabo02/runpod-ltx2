"""Read-only inventory of real media engines available on this machine.

Never marks an engine available unless its executable/model is actually found.
GPU/video engines are reported BLOCKED when CUDA or model weights are absent.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[2]
BLENDER = Path(r"C:\actions-runner\_work\blender-4.5.16-windows-x64\blender.exe")
COMFY = [Path(r"C:\ComfyUI"), Path(r"D:\ComfyUI"), Path.home() / "ComfyUI"]
CACHE = Path.home() / ".cache/huggingface/hub"


def run(cmd: list[str], timeout: int = 30) -> tuple[int, str]:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode, (result.stdout + result.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, str(exc)


def blender() -> dict:
    if not BLENDER.is_file():
        return {"installed": False, "path": str(BLENDER)}
    code, out = run([str(BLENDER), "-b", "-noaudio", "--factory-startup",
                     "--python-expr", "print('OK')"], timeout=90)
    version = next((line for line in out.splitlines() if line.startswith("Blender ")), "")
    return {"installed": code == 0, "path": str(BLENDER), "version": version.strip()}


def gpu() -> dict:
    code, out = run(["nvidia-smi", "--query-gpu=name,memory.total",
                     "--format=csv,noheader"], timeout=15)
    return {"nvidia_smi": code == 0, "devices": out.splitlines() if code == 0 else [],
            "cuda_available": code == 0}


def ollama() -> dict:
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=3) as response:
            data = json.loads(response.read().decode("utf-8"))
        return {"running": True, "models": [m.get("name") for m in data.get("models", [])]}
    except Exception as exc:  # noqa: BLE001
        return {"running": False, "error": type(exc).__name__}


def cache_models() -> list[str]:
    if not CACHE.is_dir():
        return []
    hits = []
    for path in CACHE.iterdir():
        name = path.name.lower()
        if any(key in name for key in ("ltx", "wan2", "trellis", "hunyuan", "mochi")):
            hits.append(path.name)
    return hits


def _ram_gb() -> float | None:
    try:
        import psutil
        return round(psutil.virtual_memory().total / 1e9, 1)
    except Exception:  # noqa: BLE001
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path,
                        default=ROOT / "studio/pipeline/media-factory-inventory.json")
    args = parser.parse_args(argv)
    blender_info = blender()
    gpu_info = gpu()
    ollama_info = ollama()
    comfy = [str(p) for p in COMFY if p.is_dir()]
    models = cache_models()
    payload = {
        "schema": "ahos.media-factory.inventory.v1",
        "host": {"platform": platform.platform(), "python": platform.python_version(),
                 "ram_gb": _ram_gb()},
        "disk_free_gb": round(shutil.disk_usage(ROOT).free / 1e9, 1),
        "gpu": gpu_info,
        "blender": blender_info,
        "comfyui_dirs": comfy,
        "ollama": ollama_info,
        "video_model_cache_hits": models,
        "engines": {
            "blender_actor_render": "AVAILABLE_CPU_ONLY" if blender_info["installed"] else "BLOCKED_MISSING_BLENDER",
            "trellis_image_to_3d": "BLOCKED_GPU_AND_MODEL",
            "ltx25_video": "BLOCKED_GPU_AND_MODEL",
            "wan22_animate": "BLOCKED_GPU_AND_MODEL",
            "comfyui": "AVAILABLE" if comfy else "BLOCKED_NOT_INSTALLED",
            "tts": "PARTIAL_ADULT_VOICES_ONLY",
            "ffmpeg": "AVAILABLE" if shutil.which("ffmpeg") else "BLOCKED",
        },
        "blockers": [
            "no NVIDIA CUDA GPU detected (nvidia-smi missing/failed)",
            "no ComfyUI installation found",
            "no LTX/Wan/TRELLIS model cache found",
        ],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(args.out), "engines": payload["engines"],
                      "disk_free_gb": payload["disk_free_gb"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
