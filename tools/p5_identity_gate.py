"""P5 Aden adayı ön-kapısı: onaylı referans ve ücretsiz üretici yoksa üretimi engeller."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "studio" / "qa" / "p5-aden-gate.json"
DNA = ROOT / "studio" / "characters" / "aden" / "visual-dna.json"
READINESS = ROOT / "studio" / "production" / "cast-readiness.json"
MANIFEST = ROOT / "studio" / "qa" / "aden-reference-manifest.json"


def main() -> int:
    dna = json.loads(DNA.read_text(encoding="utf-8"))
    readiness = json.loads(READINESS.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    row = next(item for item in readiness["rows"] if item["character_id"] == "aden")

    dna_text = json.dumps(dna, ensure_ascii=False).lower()
    markers = {
        "star_clip": "yıldız toka" in dna_text,
        "three_freckles": "3" in dna_text and "çil" in dna_text,
        "wavy_brown_hair": "dalgalı" in dna_text and "kahve" in dna_text,
        "cobalt_blue_outfit": "kobalt" in dna_text and "mavi" in dna_text,
    }
    keyframe = next(item for item in manifest["files"]
                    if item["relative"].endswith("keyframe-girl-seed-77.png"))
    reasons = [
        "Aden için onaylı kanonik görsel referans yok (0/16 APPROVED).",
        "Mevcut keyframe NEEDS_REVISION: yıldız toka ve çiller görünmüyor.",
        "ZeroGPU kotası kapalı; ücretsiz Kontext üretimi yapılamıyor.",
        "Yerel CUDA/Blender/SDXL/IP-Adapter yok; indirme veya ücret yasak.",
        "Pollinations yalnız metin istemli 'sana' sunuyor; kimlik koruması yok.",
        "3D mesh/rig yok; gerçek 3D animasyon üretilemez.",
    ]
    payload = {
        "schema": "ahos.studio.p5-gate.v1",
        "generated_at": "2026-11-08",
        "character_id": "aden",
        "status": "BLOCKED",
        "canon_markers": markers,
        "canon_markers_complete": all(markers.values()),
        "approved_reference": False,
        "model_sheet_status": row["model_sheet"],
        "owner_approval": row["owner_approval"],
        "source_keyframe": {"path": keyframe["relative"], "sha256": keyframe["sha256"],
                             "status": "NEEDS_REVISION"},
        "generator": {
            "zero_gpu": "BLOCKED (quota)",
            "local_image_model": False,
            "local_gpu": False,
            "blender": False,
            "commercial_license": "UNVERIFIED",
        },
        "image_candidate_produced": False,
        "animation_produced": False,
        "reasons": reasons,
        "next_action": "Sahip onaylı Aden v2 referansı veya kimlik koruyan ücretsiz üretici sağlanmadan P5 üretimi başlatılmaz.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "markers": markers,
                      "approved_reference": False, "out": str(OUT)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
