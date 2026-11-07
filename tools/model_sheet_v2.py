"""Aden/Kaan v2 model sheet üretimi — kesintiden devam eden, kota kontrollü.

Sıra (Harun):
1. aden-turnaround  (önce bu; kalite kontrolünden sonra diğerleri)
2. aden-expressions
3. kaan-turnaround
4. kaan-expressions  ← GİRDİ: başarılı v2 Kaan turnaround (eski seed-80 referansı değil)

Kurallar:
- Daha önce üretilmiş ve SHA'sı manifestle eşleşen dosya **yeniden üretilmez**.
- Başarısız adım `error`/`blocked` olarak kalır; PASS sayılmaz.
- Kaan expressions, v2 turnaround yoksa/başarısızsa **başlamaz**.
- Kota bitince durur, durumu diske yazar; sonraki çalıştırma kaldığı yerden devam eder.
- Ücretli çağrı yok; token değeri loglanmaz; çıktılar private dizinde.

Kullanım:
    python tools/model_sheet_v2.py --status
    python tools/model_sheet_v2.py --dry-run
    python tools/model_sheet_v2.py
    python tools/model_sheet_v2.py --only aden-turnaround
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
SHEETS = (ROOT / "control_plane_v2" / "runtime" / "private"
          / "animation-studio" / "model-sheets")
MANIFEST = SHEETS / "model-sheets-v2-manifest.local.json"
MODEL = "black-forest-labs/FLUX.1-Kontext-Dev"
QUALITY_GATE = "aden-turnaround"


def pause_after(step_id: str, run_all: bool) -> bool:
    """Aden turnaround kalite kapısı: onaylanmadan diğer sayfalar üretilmez."""

    return not run_all and step_id == QUALITY_GATE

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
                   "cheek, visible in the views where that cheek faces the camera (front, three-quarter, side). "
                   "Do NOT paint freckles on the back view. No other changes, no text, no labels, no watermark."),
    },
    {
        "id": "aden-expressions",
        "input": "aden-expressions-kontext-seed-202.png",
        "output": "aden-expressions-v2-kontext-seed-502",
        "seed": 502,
        "depends_on": ["aden-turnaround"],
        "prompt": ("Edit this expression sheet. KEEP identical: the same 3-year-old girl, same six panels, same "
                   "expressions, same blue t-shirt collar. CHANGE only: exactly ONE small yellow star hair clip "
                   "(remove the other two) and her three tiny freckles on the left cheek, visible wherever that "
                   "cheek is turned toward the camera. No other changes, no text, no labels, no watermark."),
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
                   "clothing colors; no other changes, no text, no labels, no watermark."),
    },
    {
        "id": "kaan-expressions",
        "input": "kaan-turnaround-v2-kontext-seed-503.png",
        "input_from": "kaan-turnaround",
        "output": "kaan-expressions-v2-kontext-seed-504",
        "seed": 504,
        "depends_on": ["kaan-turnaround"],
        "prompt": ("Expression sheet of the SAME toddler boy as the input image, whose proportions now read as a "
                   "1-year-old baby: bigger head, very chubby cheeks, short neck. Six head-and-shoulders panels in a "
                   "2x3 grid on neutral light-grey: neutral calm, big happy laugh, surprised wide eyes, sad pout, "
                   "scared, curious head tilt. Identical face and short curly black hair, identical coral-red t-shirt "
                   "collar, consistent identity in all panels, same baby proportions in every panel. Soft even "
                   "lighting, professional 3D children's animation expression sheet, no text, no labels, no watermark."),
    },
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_state(path: Path = MANIFEST) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}
    payload.setdefault("schema", "ahos.model-sheet-v2.v2")
    payload.setdefault("steps", {})
    return payload


def save_state(state: dict, path: Path = MANIFEST) -> None:
    state["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, path)


def output_path(step: dict) -> Path:
    return SHEETS / f"{step['output']}.png"


def is_verified(step: dict, state: dict) -> tuple[bool, str]:
    record = (state.get("steps") or {}).get(step["id"]) or {}
    path = output_path(step)
    if record.get("status") != "ok" or not path.is_file():
        return False, "not_ok"
    actual = sha256(path)
    if actual != record.get("sha256"):
        return False, "checksum_mismatch"
    return True, "verified"


def dependency_ready(step: dict, state: dict) -> tuple[bool, str]:
    for dependency in step.get("depends_on") or []:
        dep_step = next((item for item in STEPS if item["id"] == dependency), None)
        if dep_step is None:
            return False, f"unknown_dependency:{dependency}"
        ok, reason = is_verified(dep_step, state)
        if not ok:
            return False, f"dependency_not_ready:{dependency}:{reason}"
    input_path = SHEETS / step["input"]
    if not input_path.is_file():
        return False, f"input_missing:{step['input']}"
    return True, "ready"


def plan(state: dict, selected: list[str] | None = None) -> list[dict]:
    selected = selected or []
    rows = []
    for step in STEPS:
        if selected and step["id"] not in selected:
            continue
        verified, reason = is_verified(step, state)
        if verified:
            rows.append({"id": step["id"], "action": "skip_verified", "reason": reason,
                         "path": str(output_path(step))})
            continue
        ready, why = dependency_ready(step, state)
        rows.append({"id": step["id"], "action": "run" if ready else "skip_dependency",
                     "reason": why, "path": str(output_path(step))})
    return rows


def classify(message: str) -> str:
    text = (message or "").lower()
    if "zerogpu" in text and ("quota" in text or "runs limit" in text):
        return "zerogpu_quota"
    if "greater than maximum" in text or "less than minimum" in text:
        return "invalid_parameter"
    return "provider_error"


def run_step(step: dict, state: dict, *, force: bool = False) -> dict:
    verified, _ = is_verified(step, state)
    if verified and not force:
        return {"id": step["id"], "status": "already_done"}
    target = output_path(step)
    input_path = SHEETS / step["input"]
    if not input_path.is_file():
        return {"id": step["id"], "status": "error", "reason": f"input_missing:{input_path.name}"}

    from gradio_client import Client, handle_file
    import huggingface_hub as h
    from PIL import Image

    started = time.time()
    try:
        client = Client(MODEL, verbose=False, token=h.get_token())
        result, seed = client.predict(
            input_image=handle_file(str(input_path)), prompt=step["prompt"],
            seed=step["seed"], randomize_seed=False, guidance_scale=2.5, steps=28,
            api_name="/infer")
    except Exception as exc:  # noqa: BLE001 - sağlayıcı hatası sınıflandırılır
        return {"id": step["id"], "status": "blocked" if classify(str(exc)) == "zerogpu_quota" else "error",
                "reason": classify(str(exc)), "detail": str(exc)[:300],
                "seconds": round(time.time() - started, 1)}

    source = result.get("path") if isinstance(result, dict) else str(result)
    if not source or not Path(source).is_file():
        return {"id": step["id"], "status": "error", "reason": "empty_output"}

    raw = Path(source).read_bytes()
    temp = target.with_suffix(".tmp.png")
    temp.write_bytes(raw)
    Image.open(temp).convert("RGB").save(temp, format="PNG")
    os.replace(temp, target)
    digest = sha256(target)
    if target.stat().st_size <= 0:
        return {"id": step["id"], "status": "error", "reason": "zero_bytes"}
    return {"id": step["id"], "status": "ok", "path": str(target), "sha256": digest,
            "bytes": target.stat().st_size, "seed": int(seed), "model": MODEL,
            "prompt_sha256": hashlib.sha256(step["prompt"].encode("utf-8")).hexdigest(),
            "seconds": round(time.time() - started, 1)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--only", action="append", default=[])
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--all", action="store_true",
                        help="Aden turnaround kalite kapısını atla (yalnız QC sonrası)")
    args = parser.parse_args(argv)

    state = load_state()
    if args.dry_run or args.status:
        print(json.dumps({"steps": plan(state, args.only),
                          "manifest": str(MANIFEST)}, ensure_ascii=False, indent=2))
        return 0

    results = []
    blocked = False
    for step in STEPS:
        if args.only and step["id"] not in args.only:
            continue
        if blocked:
            results.append({"id": step["id"], "status": "skipped_after_block"})
            continue
        ready, why = dependency_ready(step, state)
        if not ready:
            results.append({"id": step["id"], "status": "skipped_dependency", "reason": why})
            continue
        outcome = run_step(step, state, force=args.force)
        results.append(outcome)
        state["steps"][step["id"]] = {**outcome, "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        state["blocked"] = outcome["id"] if outcome["status"] == "blocked" else None
        save_state(state)
        print(json.dumps(outcome, ensure_ascii=False))
        if outcome["status"] == "blocked":
            blocked = True
        elif outcome["status"] in {"ok", "already_done"} and pause_after(step["id"], args.all):
            state["awaiting_qc"] = step["id"]
            state["next"] = "aden-expressions (QC sonrası: --all)"
            save_state(state)
            print(json.dumps({"status": "awaiting_qc", "step": step["id"],
                              "next": state["next"],
                              "manifest": str(MANIFEST)}, ensure_ascii=False))
            return 0

    ok = sum(1 for item in results if item["status"] in {"ok", "already_done"})
    save_state(state)
    print(json.dumps({"manifest": str(MANIFEST), "ok": ok,
                      "blocked": state.get("blocked")}, ensure_ascii=False))
    return 0 if not blocked else 3


if __name__ == "__main__":
    raise SystemExit(main())
