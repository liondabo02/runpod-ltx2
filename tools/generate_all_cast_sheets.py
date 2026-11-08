"""16 karakter için aday turnaround + ifade sheet üretimi (ücretsiz kota, onay yok)."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import huggingface_hub as h
from gradio_client import Client, handle_file
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(r"C:\actions-runner\_work\AHOS-STUDIO-16")
ROSTER = ROOT / "studio/reference/owner_accepted_roster_v1/characters"
OUT = ROOT / "studio/candidates"

CHARS = {
    "aden": (1, "3-year-old girl with round face, big dark brown eyes, three tiny freckles on her left cheek, shoulder-length wavy dark brown hair, one small yellow star hair clip, cobalt blue t-shirt with yellow kite print, navy shorts, cream sneakers with blue soles"),
    "kaan": (2, "1-year-old baby boy with very large head, short curly black hair, chubby cheeks, coral red t-shirt, navy shorts, cream baby shoes"),
    "esra": (3, "adult mother with warm face, rose-pink hijab, long beige floral coat over dusty rose dress, brown shoes"),
    "ahmet": (4, "adult father with dark eyes, short dark hair, calm face, casual shirt and dark trousers"),
    "esma": (5, "29-year-old woman with elegant face, dusty rose hijab, modest long dress; five months pregnant (temporary)"),
    "harun": (6, "30-year-old tall fit man with long dark hair, handsome warm face, casual shirt and trousers"),
    "veysel": (7, "33-year-old man with distinctly blue eyes, short dark hair, friendly face, casual shirt"),
    "oznur": (8, "31-year-old woman with warm face, teal hijab, modest long dress"),
    "salih": (9, "2-year-old boy with short dark hair, round toddler face, play clothes"),
    "medine": (10, "2-month-old baby girl with newborn proportions, sparse dark hair, simple baby outfit"),
    "davut": (11, "30-year-old heavily built man with long dark hair, round full face, broad body, casual shirt"),
    "fatos": (12, "30-year-old woman without hijab, shoulder-length chestnut hair, slim face after surgery, natural respectful look, coral and cream clothes"),
    "emos": (13, "4-year-old girl with dark hair, round preschool face, play clothes, distinct from Aden"),
    "berzan": (14, "2-year-old boy twin with short dark hair, round toddler face, play clothes"),
    "aras": (15, "2-year-old boy twin with short dark hair, round toddler face, play clothes, slightly calmer look than Berzan"),
    "ramin": (16, "1-month-old newborn boy with newborn proportions, sparse dark hair, simple baby outfit"),
}


def generate(character_id: str, index: int, desc: str) -> dict:
    out = OUT / character_id / "model-sheet"
    out.mkdir(parents=True, exist_ok=True)
    if character_id == "aden":
        return {"turnaround": str(out / "aden-turnaround-kontext-seed-1001.png"),
                "expressions": str(out / "aden-expressions-kontext-seed-1203.png"),
                "skipped": "already generated"}
    src = ROSTER / f"{index:02d}_{character_id}.png"
    client = Client("black-forest-labs/FLUX.1-Kontext-Dev", verbose=False, token=h.get_token())
    result = {}
    turn = out / f"{character_id}-turnaround-kontext-seed-{2000 + index}.png"
    if not turn.is_file():
        prompt = (f"Character turnaround model sheet of the SAME {desc} as the reference: front full body, "
                  "left profile, back, three-quarter view in a clean grid. Same face, same hair or hijab, same "
                  "clothing and body proportions. Neutral light grey studio background, soft even lighting, full "
                  "body head to feet, no text, no watermark.")
        path, seed = client.predict(input_image=handle_file(str(src)), prompt=prompt,
                                    seed=2000 + index, randomize_seed=False, guidance_scale=2.5,
                                    steps=28, api_name="/infer")
        Image.open(path).convert("RGB").save(turn)
        result["turnaround"] = str(turn)
        print("TURN", character_id, seed, flush=True)
    expr = out / f"{character_id}-expressions-kontext-seed-{3000 + index}.png"
    if not expr.is_file():
        prompt = (f"Expression sheet of the SAME {desc} as the reference, head-and-shoulders only, 15 panels in "
                  "a clean 3x5 grid on neutral light grey: neutral, happy smile, laughter, sad, tearful, angry, "
                  "surprised, scared, curious, thoughtful, excited, shy, sleepy, affectionate, disappointed. "
                  "Identical face, hair or hijab, clothing collar, age-appropriate expressions in every panel, "
                  "soft even lighting, no text, no labels, no watermark.")
        path, seed = client.predict(input_image=handle_file(str(turn)), prompt=prompt,
                                    seed=3000 + index, randomize_seed=False, guidance_scale=2.5,
                                    steps=28, api_name="/infer")
        Image.open(path).convert("RGB").save(expr)
        result["expressions"] = str(expr)
        print("EXPR", character_id, seed, flush=True)
    return result


def main() -> int:
    log = {}
    for character_id, (index, desc) in CHARS.items():
        try:
            log[character_id] = generate(character_id, index, desc)
        except Exception as exc:  # noqa: BLE001
            log[character_id] = {"error": type(exc).__name__, "detail": str(exc)[:240]}
            print("ERR", character_id, type(exc).__name__, str(exc)[:160], flush=True)
            if "ZeroGPU" in str(exc) or "quota" in str(exc).lower():
                break
        time.sleep(1)
    (OUT / "all-cast-generation-log.json").write_text(
        json.dumps(log, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("DONE", len(log), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
