"""Aden/Kaan v2 model sheet üretimi — tek komut, kota kontrollü.

Adımlar:
1. Aden turnaround retouch: TEK yıldız toka + 3 çil (Kontext).
2. Aden expression sheet retouch: aynı düzeltmeler (Kontext).
3. Kaan turnaround retouch: daha büyük kafa, kısa bacak, dolgun yanak (Kontext).
4. Kaan expression sheet: 6 panel (Kontext, v2 referanstan).

Kurallar:
- Ücretsiz ZeroGPU kotası dolduğunda `blocked` ile durur; sonsuz tekrar yok.
- Hiçbir ücretli çağrı yapmaz; token değeri loglanmaz.
- Çıktılar private model-sheets dizinine yazılır; git'e girmez.

Kullanım:
    python tools/model_sheet_v2.py --dry-run
    python tools/model_sheet_v2.py            # kota varsa dört adımı da dener
    python tools/model_sheet_v2.py --only aden-turnaround --only kaan-expressions
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
SHEETS = (ROOT / "control_plane_v2" / "runtime" / "private"
          / "animation-studio" / "model-sheets")
MANIFEST = SHEETS / "model-sheets-v2-manifest.local.json"

STEPS = [
    {
        "id": "aden-turnaround",
        "input": "aden-turnaround-kontext-seed-101-rgb.png",
        "output": "aden-turnaround-v2-kontext-seed-501",
        "seed": 501,
        "prompt": ("Edit this character model sheet. KEEP identical: the same 3-year-old girl, face, shoulder-length "
                   "wavy dark-brown hair, cobalt blue t-shirt with yellow kite print, navy shorts, cream sneakers, "
                   "2x2 front/three-quarter/side/back layout, grey background, lighting. CHANGE only: exactly ONE "
                   "small yellow star hair clip (remove the other two), and her three tiny freckles on the left "
                   "cheek clearly visible in every view. No other changes, no text, no labels, no watermark."),
    },
    {
        "id": "aden-expressions",
        "input": "aden-expressions-kontext-seed-202.png",
        "output": "aden-expressions-v2-kontext-seed-502",
        "seed": 502,
        "prompt": ("Edit this expression sheet. KEEP identical: the same 3-year-old girl, same six panels, same "
                   "expressions, same blue t-shirt collar. CHANGE only: exactly ONE small yellow star hair clip "
                   "(remove the other two) and her three tiny freckles on the left cheek clearly visible in every "
                   "panel. No other changes, no text, no labels, no watermark."),
    },
    {
        "id": "kaan-turnaround",
        "input": "kaan-turnaround-kontext-seed-303.png",
        "output": "kaan-turnaround-v2-kontext-seed-503",
        "seed": 503,
        "prompt": ("Edit this character model sheet. KEEP identical: the same toddler boy, face, short curly black "
                   "hair, coral-red t-shirt, navy shorts, cream shoes, 2x2 front/three-quarter/side/back layout, grey "
                   "background. CHANGE only his proportions to read clearly as a 1-year-old baby: bigger head, "
                   "shorter chubby legs, fuller cheeks, softer rounder belly, slightly shorter arms. Keep the same "
                   "height ordering and clothing colors; no other changes, no text, no labels, no watermark."),
    },
    {
        "id": "kaan-expressions",
        "input": "kaan-reference-flux-seed-80.png",
        "output": "kaan-expressions-v2-kontext-seed-504",
        "seed": 504,
        "prompt": ("Expression sheet of the SAME toddler boy as the input image, now with clear 1-year-old baby "
                   "proportions: bigger head, very chubby cheeks, short neck. Six head-and-shoulders panels in a 2x3 "
                   "grid on neutral light-grey: neutral calm, big happy laugh, surprised wide eyes, sad pout, scared, "
                   "curious head tilt. Identical face and short curly black hair, identical coral-red t-shirt collar, "
                   "consistent identity in all panels. Soft even lighting, professional 3D children's animation "
                   "expression sheet, no text, no labels, no watermark."),
    },
]


def classify(message: str) -> str:
    text = (message or "").lower()
    if "zerogpu" in text and ("quota" in text or "runs limit" in text):
        return "zerogpu_quota"
    if "greater than maximum" in text or "less than minimum" in text:
        return "invalid_parameter"
    return "provider_error"


def run_step(step: dict) -> dict:
    from gradio_client import Client, handle_file
    import huggingface_hub as h

    input_path = SHEETS / step["input"]
    if not input_path.is_file():
        return {"step": step["id"], "status": "missing_input", "path": str(input_path)}
    started = time.time()
    try:
        client = Client("black-forest-labs/FLUX.1-Kontext-Dev", verbose=False,
                        token=h.get_token())
        result, seed = client.predict(
            input_image=handle_file(str(input_path)), prompt=step["prompt"],
            seed=step["seed"], randomize_seed=False, guidance_scale=2.5, steps=28,
            api_name="/infer")
    except Exception as exc:  # noqa: BLE001 - sağlayıcı hatası sınıflandırılır
        return {"step": step["id"], "status": "blocked",
                "reason": classify(str(exc)), "detail": str(exc)[:300],
                "seconds": round(time.time() - started, 1)}
    source = result.get("path") if isinstance(result, dict) else str(result)
    if not source or not Path(source).is_file():
        return {"step": step["id"], "status": "error", "reason": "empty_output"}
    from PIL import Image

    target = SHEETS / f"{step['output']}.webp"
    target.write_bytes(Path(source).read_bytes())
    Image.open(target).convert("RGB").save(target.with_suffix(".png"))
    return {"step": step["id"], "status": "ok", "path": str(target),
            "seed": int(seed), "seconds": round(time.time() - started, 1)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--only", action="append", default=[])
    args = parser.parse_args(argv)

    steps = [step for step in STEPS if not args.only or step["id"] in args.only]
    if args.dry_run:
        print(json.dumps({"dry_run": True, "steps": [
            {"id": step["id"], "input": step["input"], "output": step["output"],
             "seed": step["seed"], "model": "black-forest-labs/FLUX.1-Kontext-Dev"}
            for step in steps]}, ensure_ascii=False, indent=2))
        return 0

    results = []
    blocked = None
    for step in steps:
        if blocked:
            results.append({"step": step["id"], "status": "skipped_after_block"})
            continue
        outcome = run_step(step)
        results.append(outcome)
        if outcome["status"] == "blocked" and outcome.get("reason") == "zerogpu_quota":
            blocked = outcome.get("reason")
        print(json.dumps(outcome, ensure_ascii=False))

    manifest = {"schema": "ahos.model-sheet-v2.v1",
                "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "blocked": blocked, "results": results,
                "note": "Görsel referans; 3D mesh değil. Ücret harcanmadı."}
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"manifest": str(MANIFEST), "blocked": blocked,
                      "ok": sum(1 for item in results if item["status"] == "ok")},
                     ensure_ascii=False))
    return 0 if not blocked else 3


if __name__ == "__main__":
    raise SystemExit(main())
