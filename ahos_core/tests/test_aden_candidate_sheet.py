"""P10 Aden aday model sheet/ifade sheet ve ses engeli kaydı."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "studio" / "candidates" / "aden" / "model-sheet"
MANIFEST = json.loads((BASE / "model-sheet-manifest.json").read_text(encoding="utf-8"))
sys.path.insert(0, str(ROOT / "tools"))

import identity_lock  # noqa: E402


def test_candidate_sheet_has_five_views_and_fifteen_expressions():
    sheet = Image.open(BASE / "ADEN-model-sheet-candidate-v1.png")
    expressions = Image.open(BASE / "ADEN-expressions-candidate-v1.png")
    assert sheet.size == (1920, 1090)
    assert expressions.width >= 1000 and expressions.height >= 900
    assert MANIFEST["views"] == 5
    assert MANIFEST["expression_panels"] == 15


def test_candidate_is_pending_and_never_approved():
    assert MANIFEST["status"] == "CANDIDATE_PENDING_REVIEW"
    assert MANIFEST["owner_approval"] == "NONE"
    assert MANIFEST["final_use_allowed"] is False
    assert MANIFEST["identity_lock_modified"] is False
    assert "APPROVED" not in json.dumps(MANIFEST, ensure_ascii=False)


def test_commercial_license_is_flagged_non_commercial():
    assert "NON-COMMERCIAL" in MANIFEST["model_license"]
    assert MANIFEST["model"] == "black-forest-labs/FLUX.1-Kontext-Dev"


def test_asset_hashes_match_manifest():
    for row in MANIFEST["assets"]:
        path = ROOT / row["path"]
        assert path.is_file(), path
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"], path


def test_identity_markers_recorded_and_lock_untouched():
    markers = MANIFEST["identity_markers"]
    assert all(markers.values())
    assert identity_lock.verify() == []


def test_voice_blocker_is_recorded():
    text = (ROOT / "studio" / "qa" / "p10-voice-blocked.md").read_text(encoding="utf-8")
    assert "BLOCKED" in text and "yetişkin kadın" in text
    assert "tr-TR-EmelNeural" in text
