"""P2: merchandising dürüstlüğü ve Aden referans kaydı."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STUDIO = ROOT / "studio"


def test_merchandising_has_no_fake_assets_or_licenses():
    registry = json.loads((STUDIO / "merchandising" / "registry.json").read_text(encoding="utf-8"))
    assert registry["character_count"] == 16
    assert len(registry["characters"]) == 16
    for row in registry["characters"]:
        assert row["stl"] is None and row["glb"] is None
        assert row["licensing"]["commercial_use"] == "OWNER_APPROVAL_REQUIRED"
        assert row["licensing"]["ai_model_license"] == "UNVERIFIED"
        assert row["approved_design"] == "NONE"
    assert registry["summary"]["with_stl"] == 0
    assert registry["summary"]["approved_designs"] == 0


def test_aden_manifest_records_hashes_and_technical_specs():
    manifest = json.loads((STUDIO / "qa" / "aden-reference-manifest.json").read_text(encoding="utf-8"))
    assert manifest["originals_modified"] is False
    assert len(manifest["files"]) == 2
    keyframe, video = manifest["files"]
    assert keyframe["width"] == 1280 and keyframe["height"] == 720
    assert len(keyframe["sha256"]) == 64
    assert video["video"]["width"] == 1920 and video["video"]["height"] == 1080
    assert video["video"]["fps"] == "24/1" and video["video"]["duration_seconds"] == "5.000000"
    assert len(video["sha256"]) == 64


def test_aden_originals_still_match_recorded_hashes():
    manifest = json.loads((STUDIO / "qa" / "aden-reference-manifest.json").read_text(encoding="utf-8"))
    for row in manifest["files"]:
        path = Path(row["path"])
        if not path.is_file():
            continue  # başka makinede orijinal medya yoksa kayıt doğrulanamaz
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest == row["sha256"], path.name


def test_aden_review_marks_needs_revision_and_preview_exists():
    review = (STUDIO / "qa" / "aden-reference-review.md").read_text(encoding="utf-8")
    assert "NEEDS_REVISION" in review
    assert "yıldız toka" in review and "çil" in review
    assert (STUDIO / "qa" / "aden-preview.html").is_file()
    assert (STUDIO / "qa" / "evidence" / "aden-take2-frame-2s.png").is_file()
