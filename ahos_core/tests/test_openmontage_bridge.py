"""OpenMontage köprüsü: envanter dürüstlüğü, props şeması, canlı maliyet kapısı."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INTEGRATION = ROOT / "studio" / "integration"


def load(name: str) -> dict:
    return json.loads((INTEGRATION / name).read_text(encoding="utf-8"))


def test_bridge_maps_all_16_characters_without_approvals():
    bridge = load("openmontage-bridge.json")
    rows = bridge["character_map"]
    assert len(rows) == 16
    assert len({row["character_id"] for row in rows}) == 16
    assert all(row["owner_approval"] == "NONE" for row in rows)
    assert {row["character_id"] for row in rows if row["use_in_opening"]} == {"aden", "kaan"}
    assert bridge["target"]["license"] == "AGPLv3"
    assert "character-animation.yaml" in bridge["target"]["pipeline"]


def test_first_output_is_not_claimed_as_rendered_video():
    bridge = load("openmontage-bridge.json")
    candidate = bridge["first_output_candidate"]
    assert candidate["status"] == "PROPS_READY_RENDER_BLOCKED"
    assert "props" in candidate["props"]
    assert all("video" not in blocker.lower() or "yok" in blocker.lower()
               for blocker in bridge["blockers"])


def test_opening_props_cover_30_seconds_in_six_cards():
    props = load("openmontage-props/s01e001-opening-storyboard.json")
    assert props["status"] == "PLACEHOLDER_NOT_APPROVED"
    cuts = props["cuts"]
    assert len(cuts) == 6
    assert sum(cut["out_seconds"] - cut["in_seconds"] for cut in cuts) == 30
    assert all(cut["type"] == "text_card" and cut["source"] == "" for cut in cuts)


def test_inventory_distinguishes_files_from_running_services():
    inventory = load("openmontage-inventory.json")
    systems = {row["name"]: row for row in inventory["systems"]}
    assert systems["OpenMontage"]["files_present"] is True
    assert systems["OpenMontage"]["runnable"]["remotion_render"] == "BLOCKED"
    assert systems["RunPod endpoint"]["status"] == "CONFIGURED_UNREACHABLE"
    assert systems["Oracle instance"]["evidence"]["ssh_22"] is True
    assert systems["Oracle instance"]["evidence"]["ollama_11434"] is False
    assert systems["Pre-downloaded models"]["evidence"]["sdxl"] is False


def test_live_llm_gate_is_wired_into_executor():
    source = (ROOT / "ahos_core" / "ahos" / "llm_executor.py").read_text(encoding="utf-8")
    assert "_studio_budget_preflight" in source
    assert source.index("_studio_budget_preflight(system_prompt") < source.index("names = [settings.model")
