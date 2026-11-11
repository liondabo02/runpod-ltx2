"""P12-B: real Blender character_model backend, dispatcher, library reuse."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from ahos_studio_dispatcher import dispatch, dispatch_stage  # noqa: E402
from ahos_text_to_cartoon import parse_story  # noqa: E402

LIB = ROOT / "studio" / "assets" / "character-library" / "aden" / "v1"
MANIFEST = json.loads((LIB / "model-manifest.json").read_text(encoding="utf-8"))
BACKEND = ROOT / "tools" / "studio_backends" / "character_model_backend.py"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_library_contains_real_blend_glb_and_six_previews():
    blend = LIB / "aden-character-v1.blend"
    glb = LIB / "aden-character-v1.glb"
    assert blend.is_file() and glb.is_file()
    assert blend.read_bytes()[:7] == b"BLENDER"
    assert glb.read_bytes()[:4] == b"glTF"
    assert MANIFEST["technical_status"] == "TECHNICAL_MODEL_CREATED"
    assert MANIFEST["identity_status"] == "PENDING_IDENTITY_REVIEW"
    assert MANIFEST["rig_status"] == "NOT_STARTED"
    assert MANIFEST["stats"]["objects"] >= 20
    assert MANIFEST["stats"]["vertices"] >= 5000
    assert len(list((LIB / "previews").glob("*.png"))) == 6
    assert MANIFEST["identity_status"] != "IDENTITY_APPROVED"
    reopened = json.loads((LIB / "reopen-stats.json").read_text(encoding="utf-8"))
    assert reopened["objects"] == MANIFEST["stats"]["objects"]
    assert reopened["vertices"] == MANIFEST["stats"]["vertices"]
    assert reopened["faces"] == MANIFEST["stats"]["faces"]


def test_backend_reuses_library_and_verifies_artifacts(tmp_path):
    job = tmp_path / "job"
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"cast": ["aden"], "title": "Aden"}), encoding="utf-8")
    evidence_path = job / "character_model-evidence.json"
    run = subprocess.run([sys.executable, str(BACKEND), "--plan", str(plan),
                          "--job-dir", str(job), "--evidence", str(evidence_path)],
                         capture_output=True, text=True, timeout=120)
    assert run.returncode == 0, run.stderr
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["reused_existing_model"] is True
    assert evidence["identity_status"] == "PENDING_IDENTITY_REVIEW"
    assert evidence["cost_eur"] == 0
    for artifact in evidence["artifacts"]:
        path = job / artifact["path"]
        assert path.is_file() and sha(path) == artifact["sha256"]


def test_backend_rejects_plan_without_supported_character(tmp_path):
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"cast": ["kaan"]}), encoding="utf-8")
    run = subprocess.run([sys.executable, str(BACKEND), "--plan", str(plan),
                          "--job-dir", str(tmp_path / "job"),
                          "--evidence", str(tmp_path / "e.json")],
                         capture_output=True, text=True, timeout=60)
    assert run.returncode == 2
    assert "aden" in run.stderr


def test_dispatcher_verifies_character_model_stage(tmp_path):
    result = dispatch_stage({"cast": ["aden"]}, tmp_path / "job", "character_model")
    assert result["status"] == "VERIFIED_TECHNICAL"
    assert result["production_ready"] is False
    assert result["stages"][0]["stage"] == "character_model"


def test_full_dispatch_advances_then_blocks_at_rig(tmp_path):
    result = dispatch(parse_story("Aden ve Kaan bahçede", 6), tmp_path / "job")
    assert result["status"] == "BLOCKED"
    assert result["stages"][0]["stage"] == "character_model"
    assert result["stages"][0]["status"] == "VERIFIED_TECHNICAL"
    assert result["stages"][1]["stage"] == "rig"
    assert result["stages"][1]["status"] == "BLOCKED"
    assert result["production_ready"] is False
