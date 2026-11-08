"""P5 kapısı: onaylı referans yokken görsel/animasyon üretilmediğini doğrular."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STUDIO = ROOT / "studio"
GATE = json.loads((STUDIO / "qa" / "p5-aden-gate.json").read_text(encoding="utf-8"))


def test_gate_blocks_without_approved_reference():
    assert GATE["status"] == "BLOCKED"
    assert GATE["approved_reference"] is False
    assert GATE["image_candidate_produced"] is False
    assert GATE["animation_produced"] is False
    assert GATE["model_sheet_status"] == "NEEDS_REVISION"


def test_all_four_identity_markers_exist_in_dna():
    assert GATE["canon_markers"] == {"star_clip": True, "three_freckles": True,
                                     "wavy_brown_hair": True, "cobalt_blue_outfit": True}
    assert GATE["canon_markers_complete"] is True


def test_no_fake_p5_media_was_created():
    media = [path for path in (STUDIO / "qa").rglob("p5-*")
             if path.suffix.lower() in {".mp4", ".webm", ".mov", ".png", ".jpg", ".jpeg"}]
    assert media == []
    report = (STUDIO / "qa" / "p5-aden-blocked.md").read_text(encoding="utf-8")
    assert "BLOCKED" in report
    assert "VIDEO_READY" not in report and "IMAGE_GENERATED" not in report


def test_prior_animatic_and_tests_are_preserved():
    assert (ROOT / "deliverables" / "S01E001-OPEN-30s-ANIMATIC"
            / "S01E001-OPEN-30s-ANIMATIC-1080p24.mp4").is_file()
    assert (ROOT / "ahos_core" / "tests" / "test_animatic_output.py").is_file()


def test_cost_guard_remains_enabled():
    source = (ROOT / "ahos_core" / "ahos" / "llm_executor.py").read_text(encoding="utf-8")
    assert 'AHOS_STUDIO_COST_GUARD", "1"' in source
