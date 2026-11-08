"""Merchandising hazırlık kaydı — gerçek olmayan ürün dosyası üretmez."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDIO = ROOT / "studio"
OUT = STUDIO / "merchandising"


def main() -> int:
    cast = json.loads((STUDIO / "canon" / "cast-manifest.json").read_text(encoding="utf-8"))
    rows = []
    for row in cast["characters"]:
        cid = row["character_id"]
        rows.append({
            "character_id": cid, "display_name": row["display_name"], "age_stage": row["age_stage"],
            "model_sheet": "NEEDS_REVISION" if cid in {"aden", "kaan"} else "MISSING",
            "turnaround_views": "MISSING",
            "technical_drawings": "MISSING",
            "stl": None, "glb": None,
            "plush_spec": "PLANNED", "figure_spec": "PLANNED",
            "book_spec": "PLANNED", "apparel_spec": "PLANNED",
            "color_palette_status": "READY_FOR_QA" if cid in {"aden", "kaan"} else "MISSING",
            "scale_ratio": "READY_FOR_QA" if cid == "aden" else "MISSING",
            "licensing": {
                "character_ip": "AHOS / owner",
                "ai_model_license": "UNVERIFIED",
                "commercial_use": "OWNER_APPROVAL_REQUIRED",
                "source_rights": "UNVERIFIED",
            },
            "approved_design": "NONE",
        })
    payload = {
        "schema": "ahos.studio.merchandising.v1",
        "generated_at": "2026-11-08",
        "character_count": len(rows),
        "rule": "Model sheet/STL/GLB yoksa üretilmiş sayılmaz; AI model lisansı doğrulanmadan ticari kullanım yok.",
        "characters": rows,
        "summary": {"with_model_sheet": 0, "with_turnaround": 0, "with_stl": 0,
                    "licensed_for_commerce": 0, "approved_designs": 0},
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "registry.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                                       encoding="utf-8")

    schema = {
        "schema": "ahos.studio.merch-spec-schema.v1",
        "required": ["character_id", "product_type", "views", "dimensions_mm", "palette",
                     "materials", "safety_notes", "license_ref", "approval_ref"],
        "product_types": ["plush", "figure", "book", "apparel"],
        "views": ["front", "back", "left", "right", "three_quarter"],
        "note": "Teknik çizim ve STL/GLB yoksa alanlar null bırakılır.",
    }
    (OUT / "spec-schema.json").write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n",
                                          encoding="utf-8")
    (OUT / "README.md").write_text(
        "# Merchandising hazırlığı\n\n"
        "16 karakter için ürün kayıt iskeleti. **Gerçek model sheet, turnaround, teknik çizim, "
        "STL veya GLB yoktur.**\n\n"
        "- `registry.json`: karakter başına durum ve lisans alanları.\n"
        "- `spec-schema.json`: peluş/figür/kitap/giyim için zorunlu alanlar.\n"
        "- Ticari kullanım: AI model lisansı doğrulanana ve sahip onayı alınana kadar **yasak**.\n",
        encoding="utf-8")
    print(json.dumps({"characters": len(rows), "out": str(OUT)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
