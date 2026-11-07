"""Karakter referans görselleri üretir (ücretsiz, anahtarsız: Pollinations/Flux).

Kurallar:
- Yalnız *referans* üretir; final sahne/render değildir.
- Her görsel için prompt, seed, URL, bayt ve SHA-256 manifeste yazılır.
- Ücretli API veya hesap kullanmaz; ağ hatasında yeniden dener ve durur.

Kullanım:
    python tools/reference_sheet.py --target aden --seed 17
    python tools/reference_sheet.py --target kaan --seed 23
    python tools/reference_sheet.py --target scene --seed 7 --width 1280 --height 720
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
CHARACTERS = ROOT / "characters"
DEFAULT_OUT = ROOT / "assets" / "reference"
ENDPOINT = "https://image.pollinations.ai/prompt/"
STYLE = ("professional cinematic 3D children's animation character design, stylized Pixar-quality render, "
         "soft subsurface skin, felt-like fabrics, clean studio lighting, neutral warm-grey background, "
         "full body, front view, A-pose, no text, no watermark")


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _prompt_for(target: str) -> tuple[str, str]:
    if target in {"aden", "kaan"}:
        canon = _load(CHARACTERS / f"{target}.json")
        name = canon["name"]
        return (
            f"Character turnaround reference sheet of {canon['prompt_fragment']}. "
            f"Three views in one image: front view, three-quarter side view, back view, same character, "
            f"identical colors and proportions, standing on a neutral seamless background. {STYLE}",
            f"{target}-turnaround",
        )
    scene = _load(CHARACTERS / "scenes" / "park-kite-01.json")
    aden = _load(CHARACTERS / "aden.json")["prompt_fragment"]
    kaan = _load(CHARACTERS / "kaan.json")["prompt_fragment"]
    return (
        f"{scene['prompts']['keyframe']}. Character continuity: {aden}; {kaan}. "
        f"Original character design, cinematic composition, 16:9.",
        "park-kite-keyframe",
    )


def _build_url(prompt: str, *, width: int, height: int, seed: int) -> str:
    # Ücretsiz kademe yalnız 512 px ve varsayılan modeli kabul ediyor;
    # `model=` veya `enhance=` parametreleri 402 (Payment Required) döndürüyor.
    query = urllib.parse.urlencode({
        "width": width, "height": height, "seed": seed, "nologo": "true",
    })
    return ENDPOINT + urllib.parse.quote(prompt, safe="") + "?" + query


def _fetch(url: str, attempts: int = 3, timeout: float = 150.0) -> bytes:
    last = ""
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as response:
                data = response.read()
            if data[:3] in (b"\xff\xd8\xff",) or data[:8].startswith(b"\x89PNG"):
                return data
            last = f"unexpected content type ({len(data)} bytes)"
        except urllib.error.HTTPError as exc:
            if exc.code == 402:
                raise RuntimeError(
                    "Pollinations ücretsiz kademe reddi (HTTP 402): yalnız 512 px "
                    "ve varsayılan model. Ücretli kademe/anahtar gerekir."
                ) from exc
            last = f"{type(exc).__name__}: {exc}"
        except Exception as exc:  # noqa: BLE001 - ağ hatası yeniden denenir
            last = f"{type(exc).__name__}: {exc}"
        time.sleep(2 * attempt)
    raise RuntimeError(f"reference image could not be fetched: {last}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, choices=["aden", "kaan", "scene"])
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--variants", type=int, default=1)
    parser.add_argument("--width", type=int, default=512)
    parser.add_argument("--height", type=int, default=512)
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args(argv)

    prompt, slug = _prompt_for(args.target)
    out_dir = Path(args.out) / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for index in range(max(1, args.variants)):
        seed = args.seed + index
        url = _build_url(prompt, width=args.width, height=args.height, seed=seed)
        data = _fetch(url)
        path = out_dir / f"seed-{seed}.png"
        path.write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        records.append({"path": str(path), "seed": seed, "bytes": len(data),
                        "sha256": digest, "prompt": prompt, "url_host": "image.pollinations.ai"})
        print(json.dumps({"saved": str(path), "seed": seed, "bytes": len(data),
                          "sha256": digest[:16]}, ensure_ascii=False))

    manifest_path = out_dir / "manifest.json"
    previous = []
    if manifest_path.is_file():
        try:
            previous = json.loads(manifest_path.read_text(encoding="utf-8")).get("assets", [])
        except (OSError, json.JSONDecodeError):
            previous = []
    manifest = {
        "schema": "ahos.reference-assets.v1",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "provider": "pollinations.ai (Flux)",
        "cost_usd": 0.0,
        "note": "Yalnız karakter referansı; final sahne değildir.",
        "assets": previous + records,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"manifest": str(manifest_path), "assets": len(manifest["assets"])},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
