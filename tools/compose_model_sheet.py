"""Model sheet'leri etiketler ve manifest yazar (görsel referans; 3D mesh değil)."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
OUT = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\control_plane_v2\runtime\private"
           r"\animation-studio\model-sheets")
FONT = r"C:\Windows\Fonts\arial.ttf"
BOLD = r"C:\Windows\Fonts\arialbd.ttf"


def font(size: int, bold: bool = False):
    try:
        return ImageFont.truetype(BOLD if bold else FONT, size)
    except OSError:
        return ImageFont.load_default()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def label_sheet(source: Path, target: Path, *, title: str, subtitle: str,
                labels: list[str], columns: int, footer: str) -> Path:
    image = Image.open(source).convert("RGB")
    width = 1000
    scale = width / image.width
    image = image.resize((width, int(image.height * scale)), Image.LANCZOS)
    header = 110
    footer_h = 70
    canvas = Image.new("RGB", (width, header + image.height + footer_h), (242, 242, 242))
    canvas.paste(image, (0, header))
    draw = ImageDraw.Draw(canvas)
    draw.text((30, 22), title, fill=(20, 20, 20), font=font(34, True))
    draw.text((30, 68), subtitle, fill=(70, 70, 70), font=font(20))
    rows = (len(labels) + columns - 1) // columns
    cell_w = width / columns
    cell_h = image.height / rows
    for index, label in enumerate(labels):
        col, row = index % columns, index // columns
        x = int(col * cell_w + 16)
        y = int(header + row * cell_h + 10)
        draw.rounded_rectangle([x, y, x + 150, y + 30], radius=6, fill=(255, 255, 255))
        draw.text((x + 10, y + 5), label, fill=(30, 30, 30), font=font(18, True))
    draw.text((30, header + image.height + 20), footer, fill=(90, 90, 90), font=font(17))
    canvas.save(target)
    return target


def main() -> int:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    records = []

    def record(path: Path, kind: str, model: str, seed: int, prompt: str) -> None:
        records.append({"kind": kind, "path": str(path), "sha256": sha256(path),
                        "bytes": path.stat().st_size, "model": model, "seed": seed,
                        "prompt": prompt, "created_at": now})

    aden_turn = OUT / "aden-turnaround-kontext-seed-101-rgb.png"
    aden_expr = OUT / "aden-expressions-kontext-seed-202.png"
    kaan_turn = OUT / "kaan-turnaround-kontext-seed-303.png"
    kaan_ref = OUT / "kaan-reference-flux-seed-80.png"

    label_sheet(aden_turn, OUT / "ADEN-turnaround-labeled-v1.png",
                title="ADEN — 3 yas, kiz — karakter turu v1",
                subtitle="Ayni yuz, sac, kiyafet ve oran; 2x2 gorunus. Gorsel referans (3D mesh/rig degil).",
                labels=["ON", "3/4", "YAN", "ARKA"], columns=2,
                footer="Model: FLUX.1-Kontext-Dev · seed 101 · kaynak: aden-reference-flux-seed-78 · 2026-11-07")
    label_sheet(aden_expr, OUT / "ADEN-expressions-labeled-v1.png",
                title="ADEN — ifade sheet v1",
                subtitle="Altı temel ifade; ayni kimlik. Gorsel referans.",
                labels=["NOTR", "MUTLU", "SASKIN", "UZGUN", "KORKU", "MERAK"], columns=3,
                footer="Model: FLUX.1-Kontext-Dev · seed 202 · 2026-11-07")
    label_sheet(kaan_turn, OUT / "KAAN-turnaround-labeled-v1.png",
                title="KAAN — 1 yas, erkek — karakter turu v1",
                subtitle="Ayni yuz, sac, kiyafet ve oran; 2x2 gorunus. Gorsel referans (3D mesh/rig degil).",
                labels=["ON", "3/4", "YAN", "ARKA"], columns=2,
                footer="Model: FLUX.1-Kontext-Dev · seed 303 · kaynak: kaan-reference-flux-seed-80 · 2026-11-07")

    # Kaan ifade sheet: kota nedeniyle uretilmedi -> acik placeholder.
    placeholder = Image.new("RGB", (1000, 720), (235, 235, 235))
    draw = ImageDraw.Draw(placeholder)
    draw.text((40, 40), "KAAN — ifade sheet", fill=(30, 30, 30), font=font(34, True))
    draw.text((40, 100), "DURUM: URETILMEDI (ZeroGPU kotasi tukendi).", fill=(150, 30, 30), font=font(24, True))
    draw.text((40, 150), "Altı ifade (notr, mutlu, saskin, uzgun, korku, merak) icin bir Kontext cagrisi gerekiyor.",
              fill=(60, 60, 60), font=font(20))
    draw.text((40, 200), "Ucret harcanmadi; ucretsiz kotala tekrar denenecek veya onayli API kullanilacak.",
              fill=(60, 60, 60), font=font(20))
    placeholder.save(OUT / "KAAN-expressions-PENDING-v1.png")

    for path, kind, model, seed in (
            (OUT / "aden-reference-flux-seed-78.png", "reference", "FLUX.1-schnell", 78),
            (aden_turn, "turnaround_source", "FLUX.1-Kontext-Dev", 101),
            (aden_expr, "expressions_source", "FLUX.1-Kontext-Dev", 202),
            (kaan_ref, "reference", "FLUX.1-schnell", 80),
            (kaan_turn, "turnaround_source", "FLUX.1-Kontext-Dev", 303),
            (OUT / "ADEN-turnaround-labeled-v1.png", "sheet", "PIL composite", 0),
            (OUT / "ADEN-expressions-labeled-v1.png", "sheet", "PIL composite", 0),
            (OUT / "KAAN-turnaround-labeled-v1.png", "sheet", "PIL composite", 0),
            (OUT / "KAAN-expressions-PENDING-v1.png", "placeholder", "PIL", 0)):
        record(path, kind, model, seed, "")

    manifest = {
        "schema": "ahos.model-sheet.v1",
        "generated_at": now,
        "canon_version": "characters/v1 (Aden female, Kaan male)",
        "note": "Gorsel referans; 3D mesh/rig uretilmedi. Model sheet olarak adlandirilir.",
        "characters": {
            "aden": {"age": 3, "gender": "female", "status": "turnaround+expressions"},
            "kaan": {"age": 1, "gender": "male", "status": "turnaround; expressions PENDING (quota)"},
        },
        "assets": records,
    }
    target = OUT / "model-sheets-manifest.local.json"
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"manifest": str(target), "assets": len(records)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
