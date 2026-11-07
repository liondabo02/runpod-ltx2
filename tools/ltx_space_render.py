"""LTX-2.5 (Hugging Face Space) ile tek sahne üretimi — anahtarsız, ücretsiz kademe.

Akış:
  1. (isteğe bağlı) FLUX.1-schnell Space ile keyframe üretir.
  2. Resmî `Lightricks/LTX-2.5` Space'ine image-to-video isteği gönderir (max 5 sn).
  3. Ham MP4'ü ve üretim manifestini yazar.

Sınırlar:
- Space'te süre **en fazla 5,0 sn**; çözünürlük 512–1536.
- Ücretsiz (anonim) ZeroGPU kotası günlük birkaç çalıştırmadır; kota bitince
  araç `blocked: zerogpu_quota` ile durur ve harcama/hesap açmaz.
- Anahtar gerekmez; anahtar verilirse `HF_TOKEN` ortam değişkeni okunur.

Kullanım:
    python tools/ltx_space_render.py --keyframe deliverables/.../keyframe.png --tag take1
    python tools/ltx_space_render.py --generate-keyframe --seed 11 --tag take1
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
SCENE = ROOT / "characters" / "scenes" / "park-kite-01.json"
ENV_FILE = ROOT / ".env.runtime"
LTX_SPACE = "Lightricks/LTX-2.5"
FLUX_SPACE = "black-forest-labs/FLUX.1-schnell"
MAX_DURATION = 5.0


def load_env(path: Path = ENV_FILE) -> None:
    """`.env.runtime` içinden yalnız HF_TOKEN'ı süreç ortamına alır (repoya yazılmaz)."""

    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() in {"HF_TOKEN", "HUGGINGFACE_TOKEN"}:
            os.environ.setdefault("HF_TOKEN", value.strip().strip('"').strip("'"))


class QuotaExceeded(RuntimeError):
    pass


def classify_error(message: str) -> str:
    lowered = (message or "").lower()
    if "zerogpu" in lowered and ("quota" in lowered or "runs limit" in lowered):
        return "zerogpu_quota"
    if "greater than maximum" in lowered:
        return "invalid_parameter"
    if "queue" in lowered and "full" in lowered:
        return "queue_full"
    return "provider_error"


def build_keyframe_prompt(scene: dict | None = None, variant: str = "default") -> str:
    scene = scene or json.loads(SCENE.read_text(encoding="utf-8"))
    if variant == "baby" and scene["prompts"].get("keyframe_baby_focus"):
        return scene["prompts"]["keyframe_baby_focus"]
    return scene["prompts"]["keyframe"]


def build_video_prompt(scene: dict | None = None) -> str:
    scene = scene or json.loads(SCENE.read_text(encoding="utf-8"))
    return scene["prompts"]["image_to_video"]


def _client(space: str):
    try:
        from gradio_client import Client
    except ImportError as exc:  # pragma: no cover - ortam bağımlılığı
        raise SystemExit("gradio_client kurulu değil: pip install gradio_client") from exc
    token = os.getenv("HF_TOKEN", "").strip() or None
    return Client(space, verbose=False, token=token)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def generate_keyframe(*, seed: int, width: int, height: int, out_dir: Path,
                      variant: str = "default") -> dict:
    prompt = build_keyframe_prompt(variant=variant)
    client = _client(FLUX_SPACE)
    started = time.time()
    try:
        result, used_seed = client.predict(
            prompt=prompt, seed=seed, randomize_seed=False,
            width=width, height=height, num_inference_steps=4, api_name="/infer",
        )
    except Exception as exc:  # noqa: BLE001 - sağlayıcı hatası sınıflandırılır
        raise QuotaExceeded(classify_error(str(exc))) from exc
    source = result.get("path") if isinstance(result, dict) else str(result)
    if not source or not Path(source).is_file():
        raise RuntimeError("keyframe üretilemedi (boş çıktı)")
    data = Path(source).read_bytes()
    path = out_dir / f"keyframe-seed-{int(used_seed)}.webp"
    path.write_bytes(data)
    # Okunabilirlik için PNG kopyası (WebP ham çıktı olarak korunur).
    try:
        from PIL import Image

        Image.open(path).convert("RGB").save(path.with_suffix(".png"))
    except Exception:  # noqa: BLE001 - dönüştürme isteğe bağlı
        pass
    return {"path": str(path), "seed": int(used_seed), "bytes": len(data),
            "sha256": _sha256(path), "seconds": round(time.time() - started, 1),
            "provider": FLUX_SPACE, "prompt": prompt}


def generate_video(*, keyframe: Path, seed: int, duration: float,
                   width: int, height: int, decoder: str, out_dir: Path,
                   tag: str) -> dict:
    from gradio_client import handle_file

    if duration > MAX_DURATION:
        raise ValueError(f"Space en fazla {MAX_DURATION} sn kabul ediyor")
    prompt = build_video_prompt()
    client = _client(LTX_SPACE)
    started = time.time()
    try:
        output = client.predict(
            prompt=prompt, image_path=handle_file(str(keyframe)),
            height=height, width=width, duration_s=duration, seed=seed,
            decoder=decoder, auto_len=False, randomize_seed=False, do_enhance=False,
            api_name="/run",
        )
    except Exception as exc:  # noqa: BLE001
        raise QuotaExceeded(classify_error(str(exc))) from exc
    video_path = output[0] if isinstance(output, (list, tuple)) else str(output)
    if not video_path or not Path(video_path).is_file():
        raise RuntimeError("video üretilemedi (boş çıktı)")
    target = out_dir / f"park-kite-{tag}.mp4"
    target.write_bytes(Path(video_path).read_bytes())
    return {"path": str(target), "bytes": target.stat().st_size,
            "sha256": _sha256(target), "seconds": round(time.time() - started, 1),
            "provider": LTX_SPACE, "prompt": prompt,
            "prompt_sent": output[1] if len(output) > 1 else "",
            "seed_used": int(output[2]) if len(output) > 2 else seed,
            "length": output[3] if len(output) > 3 else "",
            "parameters": {"width": width, "height": height, "duration_s": duration,
                           "fps": 24, "decoder": decoder, "seed": seed,
                           "enhance": False, "cost_usd": 0.0}}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keyframe", default="")
    parser.add_argument("--generate-keyframe", action="store_true")
    parser.add_argument("--seed", type=int, default=101)
    parser.add_argument("--duration", type=float, default=5.0)
    parser.add_argument("--prompt-variant", choices=["default", "baby"], default="baby")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--decoder", choices=["diffusion", "conv"], default="diffusion")
    parser.add_argument("--tag", default="take1")
    parser.add_argument("--out", default=str(ROOT / "deliverables" / "S01-PARK-KITE-001"))
    args = parser.parse_args(argv)
    load_env()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    keyframe_dir = out_dir / "keyframes"
    keyframe_dir.mkdir(exist_ok=True)
    manifest = {"schema": "ahos.ltx-space-run.v1",
                "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "scene_id": "S01-PARK-KITE-001", "tag": args.tag, "free_tier": True}

    try:
        if args.generate_keyframe or not args.keyframe:
            manifest["keyframe"] = generate_keyframe(
                seed=args.seed, width=args.width, height=args.height,
                out_dir=keyframe_dir, variant=args.prompt_variant)
            keyframe = Path(manifest["keyframe"]["path"])
        else:
            keyframe = Path(args.keyframe)
        manifest["video"] = generate_video(
            keyframe=keyframe, seed=args.seed, duration=min(args.duration, MAX_DURATION),
            width=args.width, height=args.height, decoder=args.decoder,
            out_dir=out_dir, tag=args.tag)
        status = "ok"
    except QuotaExceeded as exc:
        manifest["blocked"] = str(exc)
        manifest["note"] = ("ZeroGPU ücretsiz kotası doldu. HF_TOKEN (ücretsiz hesap) "
                            "veya RunPod anahtarı gerekir; onaysız harcama yapılmadı.")
        status = "blocked"
    except (ValueError, RuntimeError) as exc:
        manifest["error"] = str(exc)
        status = "error"

    manifest_path = out_dir / f"run-{args.tag}.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": status, "manifest": str(manifest_path),
                      "video": (manifest.get("video") or {}).get("path"),
                      "blocked": manifest.get("blocked")}, ensure_ascii=False))
    return 0 if status == "ok" else 3 if status == "blocked" else 1


if __name__ == "__main__":
    raise SystemExit(main())
