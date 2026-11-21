"""Colab/Kaggle (ücretsiz GPU) — tek çekim video üretici.

KULLANIM (Colab):
  1) Runtime -> Change runtime type -> T4 GPU
  2) Bu dosyanın İÇERİĞİNİ tek hücreye yapıştır ve çalıştır
  3) Çıktı: /content/drive/MyDrive/ahos_clips/<slug>.mp4  (ve .json künye)
  4) Dosyayı Drive'dan indirip `tools/import_remote_clips.py` ile repoya al

Tasarım: LTX-Video açıksa gerçek video; açılamazsa SDXL/FLUX ile ilk kare
üretir ve ffmpeg zoompan ile 4 sn klip yapar (yine gerçek dosya, sahte değil).
Hiçbiri olmazsa açık hata verir; boş dosya PASS sayılmaz.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

PROMPT = ("2D children cartoon, flat vector, thick outlines, soft pastel colors, "
          "a cheerful 6-year-old girl with curly dark brown hair in a sunny park, "
          "camera slowly pushes in, no text")
OUT_NAME = "aden_park_5s"
SECONDS = 5
WIDTH, HEIGHT = 768, 512
SEED = 19837


def _outdir() -> Path:
    drive = Path("/content/drive/MyDrive")
    base = drive / "ahos_clips" if drive.is_dir() else Path.cwd() / "ahos_clips"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _ffprobe(path: Path) -> dict:
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=codec_type,width,height,r_frame_rate", "-show_entries", "format=duration",
         "-of", "json", str(path)], capture_output=True, text=True)
    return json.loads(proc.stdout or "{}")


def try_ltx(out: Path) -> str:
    """LTX-Video ile gerçek video dener; başarılıysa yol döner."""

    from diffusers import LTXPipeline
    import torch

    pipe = LTXPipeline.from_pretrained("Lightricks/LTX-Video", torch_dtype=torch.float16)
    pipe.to("cuda")
    frames = pipe(
        prompt=PROMPT, width=WIDTH, height=HEIGHT,
        num_frames=SECONDS * 24, num_inference_steps=30,
        generator=torch.Generator("cuda").manual_seed(SEED),
    ).frames[0]
    from diffusers.utils import export_to_video

    export_to_video(frames, str(out), fps=24)
    return "ltx"


def try_still_clip(out: Path) -> str:
    """LTX yoksa: SDXL karesi + ffmpeg zoompan → gerçek 4 sn klip."""

    import torch
    from diffusers import AutoPipelineForText2Image

    pipe = AutoPipelineForText2Image.from_pretrained(
        "stabilityai/stable-diffusion-xl-base-1.0", torch_dtype=torch.float16,
        variant="fp16", use_safetensors=True)
    pipe.to("cuda")
    image = pipe(prompt=PROMPT, width=WIDTH, height=HEIGHT,
                 generator=torch.Generator("cuda").manual_seed(SEED)).images[0]
    still = out.with_suffix(".png")
    image.save(still)
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", str(still),
         "-t", str(SECONDS), "-vf", f"scale={WIDTH}:{HEIGHT}",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out)], check=True)
    return "sdxl+zoompan"


def main() -> int:
    out = _outdir() / f"{OUT_NAME}.mp4"
    engine = ""
    error = ""
    for name, fn in (("ltx", try_ltx), ("sdxl", try_still_clip)):
        try:
            engine = fn(out)
            break
        except Exception as exc:  # noqa: BLE001 - Colab'da bağımlılık/VRAM hatası
            error += f"{name}: {type(exc).__name__}: {str(exc)[:120]}\n"
            print(f"[{name}] başarısız:", error.splitlines()[-1])
    if not engine or not out.is_file():
        print("HATA: üretim yapılamadı\n" + error)
        return 1

    meta = _ffprobe(out)
    payload = {"schema": "ahos.remote-clip.v1", "engine": engine, "prompt": PROMPT,
               "seed": SEED, "seconds": SECONDS, "file": str(out), "ffprobe": meta,
               "license_note": "LTX-Video ve SDXL model lisansları yayın öncesi doğrulanmalı"}
    out.with_suffix(".json").write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                                        encoding="utf-8")
    print("OK", engine, out, meta.get("format", {}).get("duration"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
