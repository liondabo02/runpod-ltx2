"""Offline S01E001 pilot guards; never touch live private media."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import studio_pilot_preflight as preflight  # noqa: E402


def _setup(tmp_path: Path):
    plan = json.loads((ROOT / "workflows" / "S01E001-pilot-30s-plan.json").read_text(encoding="utf-8"))
    folder = tmp_path / "workflows"
    folder.mkdir()
    (folder / "S01E001-pilot-30s-plan.json").write_text(
        json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    characters = tmp_path / "characters"
    characters.mkdir()
    for name, gender, age, contact in (
        ("aden", "female", 3, "koruyucu abla"),
        ("kaan", "male", 1, "ablasına hayran"),
    ):
        (characters / f"{name}.json").write_text(
            json.dumps({"character_id": name, "gender": gender, "age_years": age,
                        "body_language": {"eye_contact": contact}}, ensure_ascii=False),
            encoding="utf-8")
    return plan


def test_real_plan_is_30s_six_clips_and_still_requires_approval():
    report = preflight.evaluate(ROOT)
    assert report["planning_ready"], report["issues"]
    assert (report["scenes"], report["clips"], report["duration_seconds"]) == (3, 6, 30)
    assert report["render_allowed"] is False
    assert report["full_episode_allowed"] is False


def test_fail_closed_when_aden_gender_wrong(tmp_path):
    _setup(tmp_path)
    p = tmp_path / "characters" / "aden.json"
    obj = json.loads(p.read_text(encoding="utf-8"))
    obj["gender"] = "male"
    p.write_text(json.dumps(obj), encoding="utf-8")
    report = preflight.evaluate(tmp_path)
    assert "character_identity_mismatch:aden" in report["issues"]
    assert not report["planning_ready"]
    assert not report["render_allowed"]


def test_sha_approval_gate_with_tmp_path(tmp_path):
    plan = _setup(tmp_path)
    sheetdir = (tmp_path / "control_plane_v2" / "runtime" / "private"
                / "animation-studio" / "model-sheets")
    sheetdir.mkdir(parents=True)
    records = {}
    for ident, filename in preflight.REQUIRED_SHEETS.items():
        path = sheetdir / filename
        path.write_bytes(("visual-proof-" + ident).encode("utf-8"))
        records[ident] = {"status": "ok", "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    (sheetdir / "model-sheets-v2-manifest.local.json").write_text(
        json.dumps({"steps": records}), encoding="utf-8")
    report = preflight.evaluate(tmp_path)
    assert all(item["verified"] for item in report["v2_sheets"].values())
    assert report["render_allowed"] is False
    approval = sheetdir.parent / "pilot-owner-approval.local.json"
    approval.write_text(json.dumps({
        "episode_id": "S01E001", "plan_schema": plan["schema"], "approved": True
    }), encoding="utf-8")
    report = preflight.evaluate(tmp_path)
    assert report["render_allowed"] is True
    assert report["full_episode_allowed"] is False
    # Tampered media must immediately shut the gate.
    (sheetdir / preflight.REQUIRED_SHEETS["aden-turnaround"]).write_bytes(b"tampered")
    assert preflight.evaluate(tmp_path)["render_allowed"] is False
