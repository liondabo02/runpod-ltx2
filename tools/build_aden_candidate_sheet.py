"""Aden aday model sheet + ifade sheet birleştirici (onay vermez)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "studio" / "candidates" / "aden" / "model-sheet"
TURN = OUT / "aden-turnaround-kontext-seed-1001.png"
PROFILE = OUT / "aden-left-profile-kontext-seed-1102.png"
EXPR = OUT / "aden-expressions-kontext-seed-1203.png"
FONT = r"C:\Windows\Fonts\arial.ttf"
BOLD = r"C:\Windows\Fonts\arialbd.ttf"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def font(size: int, bold: bool = False):
    try:
        return ImageFont.truetype(BOLD if bold else FONT, size)
    except OSError:
        return ImageFont.load_default()


def bbox_of(path: Path) -> Image.Image:
    image = Image.open(path).convert("RGB")
    corner = image.getpixel((5, 5))
    pixels = image.load()
    left, top, right, bottom = image.width, image.height, 0, 0
    for y in range(0, image.height, 2):
        for x in range(0, image.width, 2):
            r, g, b = pixels[x, y]
            if abs(r - corner[0]) + abs(g - corner[1]) + abs(b - corner[2]) > 40:
                left, top = min(left, x), min(top, y)
                right, bottom = max(right, x), max(bottom, y)
    return image.crop((max(0, left - 10), max(0, top - 10),
                       min(image.width, right + 10), min(image.height, bottom + 10)))


def main() -> int:
    turnaround = Image.open(TURN).convert("RGB")
    quarter = turnaround.width // 4
    views = [turnaround.crop((i * quarter, 0, (i + 1) * quarter, turnaround.height)) for i in range(4)]
    profile_image = Image.open(PROFILE).convert("RGB")
    views.append(profile_image.crop((230, 30, 960, 840)))
    labels = ["ÖN", "SOL PROFİL", "ARKA", "3/4", "SAĞ PROFİL"]
    cell_w, cell_h, header, footer = 384, 900, 120, 70
    sheet = Image.new("RGB", (cell_w * 5, header + cell_h + footer), (244, 244, 244))
    draw = ImageDraw.Draw(sheet)
    draw.text((30, 24), "ADEN — aday model sheet v1 (onaysız)", fill=(30, 30, 30), font=font(34, True))
    draw.text((30, 70), "3 yaş kız · tek sarı yıldız toka · sol yanakta üç çil · kobalt tişört · lacivert şort",
              fill=(70, 70, 70), font=font(18))
    for index, (view, label) in enumerate(zip(views, labels)):
        view.thumbnail((cell_w - 20, cell_h - 70), Image.LANCZOS)
        x = index * cell_w + (cell_w - view.width) // 2
        y = header + 30 + (cell_h - 70 - view.height) // 2
        sheet.paste(view, (x, y))
        draw.text((index * cell_w + 16, header + cell_h - 40), label, fill=(30, 30, 30), font=font(20, True))
    draw.text((30, header + cell_h + 20), "Model: FLUX.1-Kontext-Dev · seed 1001/1102 · "
              "CANDIDATE_PENDING_REVIEW · ticari lisans: NON-COMMERCIAL (doğrulanmalı)",
              fill=(120, 30, 30), font=font(16))
    sheet_path = OUT / "ADEN-model-sheet-candidate-v1.png"
    sheet.save(sheet_path)

    expressions = Image.open(EXPR).convert("RGB")
    exp_sheet = Image.new("RGB", (expressions.width, expressions.height + 110), (244, 244, 244))
    exp_sheet.paste(expressions, (0, 110))
    d2 = ImageDraw.Draw(exp_sheet)
    d2.text((24, 20), "ADEN — aday ifade sheet (15 panel, onaysız)", fill=(30, 30, 30), font=font(30, True))
    d2.text((24, 62), "Aynı yüz/saç/toka/tişört hedefli; duygu eşlemesi insan incelemesi bekliyor.",
            fill=(80, 80, 80), font=font(17))
    exp_path = OUT / "ADEN-expressions-candidate-v1.png"
    exp_sheet.save(exp_path)

    manifest = {
        "schema": "ahos.studio.candidate-model-sheet.v1",
        "character_id": "aden",
        "status": "CANDIDATE_PENDING_REVIEW",
        "owner_approval": "NONE",
        "final_use_allowed": False,
        "identity_lock_modified": False,
        "model": "black-forest-labs/FLUX.1-Kontext-Dev",
        "model_license": "FLUX.1-Kontext-Dev NON-COMMERCIAL; commercial use not verified",
        "seed_turnaround": 1001, "seed_profile": 1102, "seed_expressions": 1203,
        "views": 5, "expression_panels": 15,
        "identity_markers": {"single_star_clip": True, "three_freckles": True,
                             "wavy_dark_brown_hair": True, "cobalt_tee_kite": True,
                             "navy_shorts": True},
        "identity_note": "Yüz tutarlılığı görsel incelemede; sahip onayı ve ticari lisans doğrulanmadı.",
        "source_reference": {"path": "studio/reference/owner_accepted_roster_v1/characters/01_aden.png",
                             "sha256": "7c26afc668a9e9e352918ed618a1ae3b20da7b9e08e76a395a7e4c4ba2c14b7e"},
        "assets": [
            {"path": str(TURN.relative_to(ROOT)), "sha256": sha(TURN)},
            {"path": str(PROFILE.relative_to(ROOT)), "sha256": sha(PROFILE)},
            {"path": str(EXPR.relative_to(ROOT)), "sha256": sha(EXPR)},
            {"path": str(sheet_path.relative_to(ROOT)), "sha256": sha(sheet_path)},
            {"path": str(exp_path.relative_to(ROOT)), "sha256": sha(exp_path)},
        ],
    }
    (OUT / "model-sheet-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"model_sheet": str(sheet_path), "expressions": str(exp_path),
                      "views": 5, "panels": 15}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
