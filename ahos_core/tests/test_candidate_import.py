"""Aday içe aktarma: onay vermez, orijinali değiştirmez, kimlik kilidini bozmaz."""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import candidate_import  # noqa: E402


def _root(tmp_path: Path) -> Path:
    target = tmp_path / "studio" / "characters" / "aden"
    target.mkdir(parents=True)
    shutil.copyfile(ROOT / "studio" / "characters" / "aden" / "visual-dna.json",
                    target / "visual-dna.json")
    return tmp_path


def test_import_creates_pending_candidate_without_approval(tmp_path):
    root = _root(tmp_path)
    image = tmp_path / "aden.png"
    Image.new("RGB", (600, 900), "#FFFFFF").save(image)
    original = hashlib.sha256(image.read_bytes()).hexdigest()

    record = candidate_import.import_candidate("aden", image, root=root, source="test")

    assert record["status"] == "CANDIDATE_PENDING_REVIEW"
    assert record["owner_approval"] == "NONE"
    assert record["final_use_allowed"] is False
    assert record["identity_lock_modified"] is False
    assert record["sha256"] == original == hashlib.sha256(image.read_bytes()).hexdigest()
    assert (root / record["path"]).is_file()
    assert record["visual_dna"]["sha256"] == hashlib.sha256(
        (root / record["visual_dna"]["path"]).read_bytes()).hexdigest()
    registry = json.loads((root / "studio" / "candidates" / "aden" / "registry.json")
                          .read_text(encoding="utf-8"))
    assert len(registry["candidates"]) == 1
    assert registry["candidates"][0]["owner_approval"] == "NONE"
    assert "APPROVED" not in json.dumps(registry)


def test_reimport_is_deduplicated(tmp_path):
    root = _root(tmp_path)
    image = tmp_path / "aden.png"
    Image.new("RGB", (600, 900), "#EEEEEE").save(image)
    candidate_import.import_candidate("aden", image, root=root)
    candidate_import.import_candidate("aden", image, root=root)
    registry = json.loads((root / "studio" / "candidates" / "aden" / "registry.json")
                          .read_text(encoding="utf-8"))
    assert len(registry["candidates"]) == 1


def test_rejects_non_image_and_small_image(tmp_path):
    root = _root(tmp_path)
    text = tmp_path / "not-image.png"
    text.write_text("hello", encoding="utf-8")
    with pytest.raises(SystemExit):
        candidate_import.import_candidate("aden", text, root=root)
    small = tmp_path / "small.png"
    Image.new("RGB", (100, 100)).save(small)
    with pytest.raises(SystemExit):
        candidate_import.import_candidate("aden", small, root=root)


def test_real_repo_candidate_media_is_only_pending_model_sheet():
    registry = json.loads((ROOT / "studio" / "candidates" / "aden" / "registry.json")
                          .read_text(encoding="utf-8"))
    assert registry["candidates"] == []
    assert registry["awaiting_import"] is True
    media = [path for path in (ROOT / "studio" / "candidates" / "aden").rglob("*")
             if path.suffix.lower() in {".png", ".jpg", ".jpeg"}]
    assert media
    assert all("model-sheet" in path.parts for path in media)
    manifest = json.loads((ROOT / "studio" / "candidates" / "aden" / "model-sheet"
                           / "model-sheet-manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "CANDIDATE_PENDING_REVIEW"
    assert manifest["owner_approval"] == "NONE"


def test_gate_allows_candidate_but_not_final():
    gate = json.loads((ROOT / "studio" / "qa" / "p5-aden-gate.json").read_text(encoding="utf-8"))
    assert gate["candidate_generation_allowed"] is True
    assert gate["final_lock_allowed"] is False
