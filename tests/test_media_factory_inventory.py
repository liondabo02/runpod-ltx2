"""Inventory must report real host capability, not optimistic placeholders."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "studio/pipeline/media-factory-inventory.json"


def test_inventory_reports_real_blockers_and_available_blender():
    data = json.loads(INVENTORY.read_text(encoding="utf-8"))
    assert data["schema"] == "ahos.media-factory.inventory.v1"
    assert data["engines"]["blender_actor_render"] == "AVAILABLE_CPU_ONLY"
    assert data["engines"]["ffmpeg"] == "AVAILABLE"
    assert data["engines"]["ltx25_video"].startswith("BLOCKED")
    assert data["engines"]["wan22_animate"].startswith("BLOCKED")
    assert data["gpu"]["cuda_available"] is False
    assert data["blockers"]
