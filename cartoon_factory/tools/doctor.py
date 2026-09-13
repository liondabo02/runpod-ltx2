from __future__ import annotations

import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check_bin(name: str, env_name: str | None = None) -> tuple[str, bool, str]:
    value = os.getenv(env_name, name) if env_name else name
    path = shutil.which(value)
    return name, bool(path), path or value


def main() -> None:
    checks = [
        check_bin("ffmpeg", "FFMPEG_BIN"),
        check_bin("piper", "PIPER_BIN"),
        check_bin("rhubarb", "RHUBARB_BIN"),
    ]
    voice_dir = Path(os.getenv("PIPER_VOICES_DIR", ROOT / "assets" / "voices"))
    voice_models = list(voice_dir.glob("c*.onnx")) if voice_dir.exists() else []
    print("Cartoon Factory doctor\n")
    for name, ok, path in checks:
        print(f"{'OK' if ok else 'MISSING':7} {name:10} {path}")
    print(f"{'OK' if len(voice_models) >= 10 else 'MISSING':7} voices     {len(voice_models)}/10 models")
    llm_key = bool(os.getenv("LLM_API_KEY")) or "localhost" in os.getenv("LLM_BASE_URL", "")
    print(f"{'OK' if llm_key else 'MISSING':7} llm        API key or local endpoint")
    rp = bool(os.getenv("RUNPOD_ENDPOINT_URL"))
    print(f"{'OK' if rp else 'OPTIONAL':7} runpod     special-shot endpoint")


if __name__ == "__main__":
    main()
