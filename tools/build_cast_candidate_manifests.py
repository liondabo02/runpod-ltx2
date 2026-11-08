"""Üretilen cast adayları için manifest yazar (onay vermez)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "studio" / "candidates"
CAST = {
    "aden": {"views": 5, "expressions": 15, "turn_seed": 1001, "expr_seed": 1203,
             "source": "01_aden.png"},
    "kaan": {"views": 4, "expressions": 12, "turn_seed": 2002, "expr_seed": 3002,
             "source": "02_kaan.png"},
    "esra": {"views": 4, "expressions": 0, "turn_seed": 2003, "expr_seed": None,
             "source": "03_esra.png"},
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


for cid, info in CAST.items():
    folder = OUT / cid / "model-sheet"
    assets = []
    for path in sorted(folder.glob("*.png")):
        assets.append({"path": str(path.relative_to(ROOT)), "sha256": sha(path)})
    manifest = {
        "schema": "ahos.studio.candidate-model-sheet.v1",
        "character_id": cid,
        "status": "CANDIDATE_PENDING_REVIEW",
        "owner_approval": "NONE",
        "final_use_allowed": False,
        "identity_lock_modified": False,
        "model": "black-forest-labs/FLUX.1-Kontext-Dev",
        "model_license": "FLUX.1-Kontext-Dev NON-COMMERCIAL; commercial use not verified",
        "views": info["views"],
        "expression_panels": info["expressions"],
        "seed_turnaround": info["turn_seed"],
        "seed_expressions": info["expr_seed"],
        "source_reference": f"studio/reference/owner_accepted_roster_v1/characters/{info['source']}",
        "assets": assets,
        "note": "Ücretsiz ZeroGPU kotası; onay yok, ticari kullanım yok.",
    }
    if cid == "aden":
        manifest["identity_markers"] = {"single_star_clip": True, "three_freckles": True,
                                        "wavy_dark_brown_hair": True, "cobalt_tee_kite": True,
                                        "navy_shorts": True}
    (folder / "model-sheet-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(cid, len(assets), info["views"], info["expressions"])
