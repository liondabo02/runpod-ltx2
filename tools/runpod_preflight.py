"""RunPod LTX-2 hattı için ön kontrol (harcama yapmaz).

Yalnız ortam değişkenlerini ve `.env.runtime` dosyasını okur; ağ çağrısı yapmaz.
Anahtarı asla yazdırmaz; yalnız "var/yok" ve endpoint kimliğini gösterir.

Kullanım:
    python tools/runpod_preflight.py
    python tools/runpod_preflight.py --payload-preview
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "ahos_core"
sys.path.insert(0, str(CORE))

ENV_FILE = ROOT / ".env.runtime"
ALLOWED = ("RUNPOD_API_KEY", "RUNPOD_LTX_ENDPOINT_ID", "RUNPOD_LTX_BASE_URL")


def load_env(path: Path = ENV_FILE) -> dict[str, str]:
    """`.env.runtime` içinden yalnız izinli anahtarları okur; süreç ortamına yazar."""

    loaded: dict[str, str] = {}
    if not path.is_file():
        return loaded
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key in ALLOWED and value:
            os.environ.setdefault(key, value)
            loaded[key] = value
    return loaded


def preflight() -> dict:
    from ahos.runpod_ltx2 import RunPodLTX2Config, RunPodLTX2Provider

    loaded = load_env()
    endpoint_id = os.getenv("RUNPOD_LTX_ENDPOINT_ID", "").strip()
    base_url = os.getenv("RUNPOD_LTX_BASE_URL", "https://api.runpod.ai/v2").strip()
    result: dict = {
        "env_file": str(ENV_FILE) if ENV_FILE.is_file() else None,
        "env_file_keys": sorted(loaded),
        "endpoint_id_present": bool(endpoint_id),
        "api_key_present": bool(os.getenv("RUNPOD_API_KEY", "").strip()),
        "ready": False,
        "spending": "blocked until explicit paid approval",
    }
    missing = [name for name, present in (
        ("RUNPOD_LTX_ENDPOINT_ID", bool(endpoint_id)),
        ("RUNPOD_API_KEY", result["api_key_present"]),
    ) if not present]
    if missing:
        result["missing"] = missing
    if not endpoint_id:
        return result
    try:
        config = RunPodLTX2Config(endpoint_id=endpoint_id, base_url=base_url)
    except ValueError as exc:
        result["error"] = f"invalid endpoint config: {exc}"
        return result
    provider = RunPodLTX2Provider(config)
    summary = provider.configuration_summary()
    # Anahtar değeri asla dışarı çıkmaz; yalnız varlık bilgisi.
    result["provider"] = {key: value for key, value in summary.items()
                          if key not in {"api_key_env"}}
    result["ready"] = bool(result["api_key_present"] and summary["endpoint_id"])
    if not result["ready"]:
        result["missing"] = [name for name, present in (
            ("RUNPOD_LTX_ENDPOINT_ID", bool(endpoint_id)),
            ("RUNPOD_API_KEY", result["api_key_present"]),
        ) if not present]
    return result


def payload_preview() -> dict:
    from ahos.runpod_ltx2 import RunPodLTX2Provider
    from ahos.visual_pipeline import RenderJob

    job = RenderJob(
        job_id="S01-PARK-KITE-001:t01", episode_id="S01-PARK-KITE-001",
        shot_id="t01", prompt_id="park-kite-v1", output_asset_id="park-kite",
        mode="video", seed=7,
        positive_prompt="Aden and Kaan fly a colorful kite in a green park, cinematic 3D children's animation",
        negative_prompt="photoreal faces, extra fingers, text, watermark",
        reference_asset_ids=("charref:aden:v1", "charref:kaan:v1"),
        continuity_constraints=("keep identity", "keep clothing colors", "keep height ratio"),
        style_id="park-kite-v1", duration_seconds=6, output_prefix="S01-PARK-KITE-001/t01/7",
    )
    # 16:9 ve 32'ye bölünebilir: 1024x576 → teslimde 1920x1080'e ölçeklenir.
    request = RunPodLTX2Provider.render_payload(job, width=1024, height=576)["input"]
    request["input_image_base64"] = "<keyframe.png → base64>"
    return request


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--payload-preview", action="store_true")
    args = parser.parse_args(argv)
    result = preflight()
    if args.payload_preview:
        result["payload_preview"] = payload_preview()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ready") else 2


if __name__ == "__main__":
    raise SystemExit(main())
