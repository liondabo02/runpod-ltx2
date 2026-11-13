"""System-level routing, repeatable series identity, and independent QA checks."""
import hashlib
import importlib.util
import json
from pathlib import Path
from unittest.mock import patch
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("studio_cinematic_router",ROOT/"tools"/"studio_cinematic_router.py")
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

H=lambda x:x*64

def bible():
    return {"schema":"ahos.series-bible.lock.v1","cast":{
      "aden":{"identity_approved":True,"commercial_rights_verified":True,
              "model_sha256":H("a"),"rig_sha256":H("b"),"voice_sha256":H("c")},
      "kaan":{"identity_approved":True,"commercial_rights_verified":True,
              "model_sha256":H("d"),"rig_sha256":H("e"),"voice_sha256":H("f")}}}

def shot(kind="dialogue",cast=None):
    cast=["aden"] if cast is None else cast
    b=bible()
    a={"shot_id":"s01e001-sc01-sh01","kind":kind,
       "cast":cast,
       "direction":"Aden gently looks toward Kaan in a stable medium shot.",
       "identity_locks":{c:{k:b["cast"][c][k] for k in mod.LOCKED} for c in cast}}
    if kind=="dialogue":
        a["dialogue_track"]={"sha256":H("1"),"language":"tr"}
    return a

def provider(engine="blender_rig",region="EU",cost=0,status="VERIFIED_RUNTIME"):
    return {engine:{"status":status,"license_status":"COMMERCIAL_REVIEWED",
                    "allowed_regions":[region],"new_spend_eur":cost,
                    "runtime_proof_sha256":H("2")}}

def qa_fixture(tmp_path):
    video=tmp_path/"render.mp4"
    video.write_bytes(b"pretend input for ffprobe stub"*5000)
    evidence=tmp_path/"independent-evidence.json"
    evidence.write_text('{"source":"second independent evaluator","frames_reviewed":120}',encoding="utf-8")
    report={"schema":"ahos.studio.independent-shot-qa.v1",
      "artifact_sha256":mod._hash_file(video),
      "reviewer":"external_independent_visual_qa",
      "human_review_or_validated_multimodal_qa":True,
      "review_evidence_sha256":mod._hash_file(evidence),
      "review_evidence_path":str(evidence),
      "identity_locks":shot()["identity_locks"],
      "shot_id":shot()["shot_id"],
      "scores":{k:1.0 for k in mod.QA_DIMENSIONS}}
    class Proc:
        stdout=json.dumps({"streams":[
          {"codec_type":"video","width":1920,"height":1080,"r_frame_rate":"24/1"},
          {"codec_type":"audio"}],"format":{"duration":"5.05"}})
    return video,report,Proc

def test_identity_reused_across_different_episodes():
    a=shot("action",["aden","kaan"])
    a["direction"]="Two kids find the kite in the park and take turns playing."
    b=shot("cinematic",["aden","kaan"])
    b["direction"]="The children discover the rainbow and smile under sunset light."
    assert mod.validate_shot(a,bible())["identity_locked"]
    assert mod.validate_shot(b,bible())["voice_locked"]

def test_reject_changed_character_face_or_voice():
    x=shot()
    x["identity_locks"]["aden"]["model_sha256"]=H("d")
    with pytest.raises(mod.ProductionBlocked,match="changed"):
        mod.validate_shot(x,bible())
    x=shot()
    x["identity_locks"]["aden"]["voice_sha256"]=H("0")
    with pytest.raises(mod.ProductionBlocked,match="changed"):
        mod.validate_shot(x,bible())

def test_unapproved_character_not_used_for_series():
    b=bible()
    b["cast"]["aden"]["identity_approved"]=False
    with pytest.raises(mod.ProductionBlocked,match="not identity-approved"):
        mod.validate_shot(shot(),b)

def test_missing_voice_in_dialogue_is_rejected():
    x=shot()
    x.pop("dialogue_track")
    with pytest.raises(mod.ProductionBlocked,match="mastered voice"):
        mod.validate_shot(x,bible())

def test_no_verified_engine_returns_honest_blocker():
    result=mod.route_shot(shot(),bible(),provider(status="NOT_PROVISIONED"))
    assert result["status"]=="WAITING_VERIFIED_ENGINE"
    assert not result["production_ready"]

def test_license_geo_and_cost_controls():
    r=mod.route_shot(shot("acting"),bible(),provider(region="US"))
    assert r["status"]=="WAITING_VERIFIED_ENGINE"
    assert "territory" in r["rejections"]["blender_rig"]
    r=mod.route_shot(shot("acting"),bible(),provider(cost=1))
    assert r["status"]=="WAITING_VERIFIED_ENGINE"

def test_scene_specific_multi_engine_routing():
    engines={}
    for name in ("blender_rig","wan22_animate","ltx25_dfr","ltx25_ingredients"):
        engines.update(provider(name))
    assert mod.route_shot(shot("dialogue"),bible(),engines)["engine"]=="blender_rig"
    assert mod.route_shot(shot("action"),bible(),engines)["engine"]=="wan22_animate"
    assert mod.route_shot(shot("establishing",[]),bible(),engines)["engine"]=="ltx25_dfr"

def test_independent_qa_acceptance_requires_real_media_and_review(tmp_path):
    video,report,Proc=qa_fixture(tmp_path)
    with patch.object(mod.shutil,"which",return_value="/usr/bin/ffprobe"),\
         patch.object(mod.subprocess,"run",return_value=Proc()):
        decision=mod.evaluate_shot(shot(),bible(),video,report,generator="blender_rig")
    assert decision["status"]=="QA_PASS"
    assert decision["media"]["has_audio"] is True
    assert decision["production_ready"] is False

def test_qa_does_not_allow_self_review_or_forged_artifact(tmp_path):
    video,report,Proc=qa_fixture(tmp_path)
    report["reviewer"]="blender_rig"
    with pytest.raises(mod.ProductionBlocked,match="independent"):
        mod.evaluate_shot(shot(),bible(),video,report,generator="blender_rig")
    report["reviewer"]="other_qa"
    video.write_bytes(b"forged video bytes"*10000)
    with pytest.raises(mod.ProductionBlocked,match="hash differs"):
        mod.evaluate_shot(shot(),bible(),video,report,generator="blender_rig")

def test_identity_failure_is_not_hidden_by_high_average(tmp_path):
    video,report,Proc=qa_fixture(tmp_path)
    report["scores"]["identity"]=0.3
    with patch.object(mod.shutil,"which",return_value="/usr/bin/ffprobe"),\
         patch.object(mod.subprocess,"run",return_value=Proc()):
        decision=mod.evaluate_shot(shot(),bible(),video,report,generator="wan22_animate")
    assert decision["status"]=="REPAIR_REQUIRED"
    fix=mod.plan_repair(decision,attempts=0)
    assert fix["re_render_scope"]=="failed shot only"
    assert fix["work_orders"]==["asset_identity_and_conditioning"]
    assert mod.plan_repair(decision,attempts=2)["status"]=="BLOCKED_NEEDS_CREATIVE_REVIEW"

def test_real_media_probe_rejects_soundless_dialogue(tmp_path):
    video=tmp_path/"video.mp4"
    video.write_bytes(b"noise"*30000)
    class Proc:
        stdout=json.dumps({"streams":[{"codec_type":"video","width":1280,"height":720}],
                           "format":{"duration":5}})
    with patch.object(mod.shutil,"which",return_value="/usr/bin/ffprobe"),\
         patch.object(mod.subprocess,"run",return_value=Proc()):
        with pytest.raises(mod.ProductionBlocked,match="audio"):
            mod.media_probe(video,dialogue=True)
