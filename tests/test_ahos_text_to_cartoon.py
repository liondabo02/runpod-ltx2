"""Regression checks for the owner-facing, zero-cost story box."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
PATH=ROOT/"tools"/"ahos_text_to_cartoon.py"
spec=importlib.util.spec_from_file_location("ahos_text_to_cartoon",PATH)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_cast_and_actions_are_detected():
    plan=module.parse_story('Aden ve Kaan bahçede uçurtma uçurur. Aden yürüyor ve el sallıyor. Kaan emekliyor.',4)
    assert plan["cast"]==["aden","kaan"]
    assert plan["actions"]["kite"]
    assert plan["actions"]["crawl"]
    assert plan["technical_preview_supported"]
    assert not plan["approved_character_assets_used"]


def test_other_cast_fails_closed_without_lying():
    plan=module.parse_story("Davut ile Ramin evde konuşuyor.",4)
    assert "davut" in plan["cast"] and "ramin" in plan["cast"]
    assert plan["technical_preview_supported"] is False
    assert any("rig'i olmayan" in x for x in plan["blockers"])


def test_unmentioned_cast_not_invented():
    plan=module.parse_story("Ormanda bir uçurtma kayboldu.",5)
    assert plan["cast"]==[]
    assert not plan["technical_preview_supported"]


def test_plan_changes_with_story():
    a=module.parse_story("Aden bahçede yürüyor ve uçurtmaya bakıyor.",5)
    b=module.parse_story("Kaan evde emekliyor.",5)
    assert a["cast"]!=b["cast"]
    assert a["setting"]!=b["setting"]
    assert a["actions"]!=b["actions"]


def test_plan_only_is_real_output_without_false_video(tmp_path):
    out=tmp_path/"sample"
    result=module.run_pipeline("Aden ve Kaan bahçede uçurtma oynuyor.",out,4,plan_only=True)
    assert result["state"]=="PLANNED"
    assert (out/"story-plan.json").exists()
    assert (out/"result.json").exists()
    assert not (out/"technical-preview.mp4").exists()
    assert not result["production_ready"]


def test_bad_inputs():
    with pytest.raises(ValueError): module.parse_story("",4)
    with pytest.raises(ValueError): module.parse_story("Aden",21)
    with pytest.raises(ValueError): module.parse_story("x"*2001,4)


def test_original_roster_remains_available():
    root=ROOT/"studio"/"reference"/"owner_accepted_roster_v1"
    assert (root/"manifest.json").is_file()
    imgs=list((root/"characters").glob("*.png"))
    assert len(imgs)==16


def test_technical_renderer_never_claims_production():
    plan=module.parse_story("Aden ve Kaan yürür, Kaan emekler.",4)
    assert plan["technical_preview_supported"]
    assert plan["approved_character_assets_used"] is False
    assert module.ENGINE.exists()
