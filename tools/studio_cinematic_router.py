"""AHOS Studio OS cinematic shot router and independent quality gate.

Purpose: preserve identity over a whole series; choose between already-verified
rig render, Wan Animate, and LTX-2.5 for different shot demands; reject fake
"Hollywood ready" claims. Standard library only; NO cloud or GPU calls.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

HEX64 = re.compile(r"^[a-f0-9]{64}$")
KINDS = frozenset(("dialogue", "acting", "action", "establishing", "cinematic", "transition"))
LOCKED = ("model_sha256", "rig_sha256", "voice_sha256")
QA_DIMENSIONS = ("identity", "acting", "motion", "continuity", "cinematography",
                 "story_adherence", "audio", "child_safety", "rights")
# Never use one aggregate average to hide a major character-identity defect.
QA_FLOORS = {"identity":0.95, "acting":0.85, "motion":0.88,
             "continuity":0.93, "cinematography":0.88,
             "story_adherence":0.90, "audio":0.90,
             "child_safety":1.0, "rights":1.0}
# Explicit preferences per shot. They are NOT quality measurements.
PREFERENCE = {
    "dialogue": {"blender_rig":100, "wan22_animate":72, "ltx25_ingredients":45},
    "acting": {"blender_rig":100, "wan22_animate":83, "ltx25_ingredients":55},
    "action": {"wan22_animate":100, "blender_rig":92, "ltx25_ingredients":75},
    "establishing": {"ltx25_dfr":100, "blender_rig":85, "ltx25_ingredients":80},
    "cinematic": {"ltx25_dfr":100, "ltx25_ingredients":90, "blender_rig":85},
    "transition": {"blender_rig":90, "ltx25_dfr":85, "ltx25_ingredients":80},
}
ENGINE_FEATURES = {
    "blender_rig": {"persistent_3d", "locked_assets", "camera_control", "motion_control", "voice_master"},
    "wan22_animate": {"locked_reference", "motion_control", "image_to_video"},
    "ltx25_ingredients": {"locked_reference", "image_to_video", "video_audio"},
    "ltx25_dfr": {"locked_reference", "image_to_video", "high_detail", "video_audio"},
}


class ProductionBlocked(ValueError):
    """A genuine unmet production precondition; do not replace with a mock."""


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda:stream.read(1024 * 1024),b""):
            h.update(chunk)
    return h.hexdigest()


def _sha(value: Any, label: str) -> str:
    if not isinstance(value,str) or not HEX64.fullmatch(value):
        raise ProductionBlocked(label+" must be an exact lowercase sha256")
    return value


def validate_series_bible(bible: dict) -> dict:
    """Resolve one canonical cast snapshot; never accept a newly generated face as canonical."""
    if not isinstance(bible,dict) or bible.get("schema")!="ahos.series-bible.lock.v1":
        raise ProductionBlocked("A locked series-bible snapshot is mandatory")
    cast=bible.get("cast")
    if not isinstance(cast,dict) or not cast:
        raise ProductionBlocked("No characters in locked series bible")
    for char, asset in cast.items():
        if not isinstance(char,str) or not char or not isinstance(asset,dict):
            raise ProductionBlocked("Invalid character record")
        if asset.get("identity_approved") is not True:
            raise ProductionBlocked("Character is not identity-approved: "+char)
        if asset.get("commercial_rights_verified") is not True:
            raise ProductionBlocked("Character lacks verified rights: "+char)
        for field in LOCKED:
            _sha(asset.get(field),char+"."+field)
    return cast


def validate_shot(shot:dict, bible:dict) -> dict:
    cast=validate_series_bible(bible)
    if not isinstance(shot,dict) or not isinstance(shot.get("shot_id"),str):
        raise ProductionBlocked("Shot ID required")
    if not re.fullmatch(r"[A-Za-z0-9_-]{3,80}",shot["shot_id"]):
        raise ProductionBlocked("Invalid shot ID")
    kind=shot.get("kind")
    if kind not in KINDS:
        raise ProductionBlocked("Shot kind unsupported")
    actors=shot.get("cast",[])
    if not isinstance(actors,list) or len(actors)!=len(set(actors)):
        raise ProductionBlocked("Shot cast must be unique")
    if not all(isinstance(x,str) and x in cast for x in actors):
        raise ProductionBlocked("Unknown or unapproved cast in shot")
    if kind in ("dialogue","acting","action") and not actors:
        raise ProductionBlocked("Actor shot has no approved actors")
    # The shot cannot silently substitute a character's model, rig or voice.
    submitted=shot.get("identity_locks",{})
    if not isinstance(submitted,dict) or set(submitted)!=set(actors):
        raise ProductionBlocked("Every actor needs all three immutable identity locks")
    for actor in actors:
        locked=submitted.get(actor)
        if not isinstance(locked,dict):
            raise ProductionBlocked("Missing locks for "+actor)
        for field in LOCKED:
            if locked.get(field)!=cast[actor][field]:
                raise ProductionBlocked("Series identity/voice changed for "+actor+"."+field)
    if not isinstance(shot.get("direction"),str) or len(shot["direction"].strip())<20:
        raise ProductionBlocked("Director has not provided a real shot instruction")
    if kind=="dialogue" and not isinstance(shot.get("dialogue_track"),dict):
        raise ProductionBlocked("Dialogue shot requires a mastered voice track")
    if kind=="dialogue":
        track=shot["dialogue_track"]
        _sha(track.get("sha256"),"Dialogue track")
        if track.get("language") not in ("tr","de","en","ar","fr","es","ku"):
            raise ProductionBlocked("Voice language unknown")
    return {"shot_id":shot["shot_id"],"kind":kind,"cast":actors,
            "identity_locked":True,"voice_locked":True}


def route_shot(shot:dict,bible:dict,providers:dict, *,
               region:str="EU", max_new_spend_eur:float=0) -> dict:
    validated=validate_shot(shot,bible)
    if not isinstance(providers,dict):
        raise ProductionBlocked("Provider registry must be an object")
    eligible=[]
    rejects={}
    for engine, cfg in providers.items():
        reason=None
        if engine not in ENGINE_FEATURES or not isinstance(cfg,dict):
            reason="unknown engine or invalid record"
        elif engine not in PREFERENCE[shot["kind"]]:
            reason="engine not qualified for this shot type"
        elif cfg.get("status")!="VERIFIED_RUNTIME":
            reason="not proven with a real executable worker"
        elif cfg.get("license_status")!="COMMERCIAL_REVIEWED":
            reason="commercial license not reviewed"
        elif region not in cfg.get("allowed_regions",[]):
            reason="license/territory does not permit this region"
        elif not isinstance(cfg.get("new_spend_eur"),(int,float)) or (
                cfg["new_spend_eur"]<0 or cfg["new_spend_eur"]>max_new_spend_eur):
            reason="new spending not authorized"
        elif not HEX64.fullmatch(str(cfg.get("runtime_proof_sha256",""))):
            reason="missing real runtime proof hash"
        elif shot["cast"] and not (
                {"locked_reference","locked_assets"} & ENGINE_FEATURES[engine]):
            reason="engine cannot consume a locked character reference"
        elif shot["kind"]=="dialogue" and not (
                {"voice_master","video_audio"} & ENGINE_FEATURES[engine]):
            reason="engine lacks a voice conditioning path"
        if reason:
            rejects[engine]=reason
        else:
            eligible.append((PREFERENCE[shot["kind"]].get(engine,30),engine))
    if not eligible:
        return {"status":"WAITING_VERIFIED_ENGINE",
                "shot_id":validated["shot_id"],"cast":validated["cast"],
                "production_ready":False,"rejections":rejects,
                "next_action":"qualify an actual identity-conditioned GPU/rig engine; never fake render"}
    _, engine=max(eligible,key=lambda x:(x[0],x[1]))
    return {"status":"READY_FOR_TECHNICAL_RENDER","shot_id":validated["shot_id"],
            "engine":engine,"cast":validated["cast"],"identity_locked":True,
            "production_ready":False,"creative_qa_required":True,
            "candidate_engines":[x[1] for x in sorted(eligible,reverse=True)],
            "rejections":rejects}


def media_probe(path: Path, *, dialogue: bool=False) -> dict:
    """Inspect *actual* media with ffprobe rather than trusting a JSON report."""
    binary=shutil.which("ffprobe")
    if binary is None:
        raise ProductionBlocked("ffprobe unavailable; rendered media not verified")
    try:
        output=subprocess.run(
            [binary,"-v","error","-show_entries",
             "format=duration:stream=codec_type,width,height,r_frame_rate",
             "-of","json",str(path)],
            capture_output=True,text=True,timeout=20,check=True)
        data=json.loads(output.stdout)
    except (subprocess.CalledProcessError,subprocess.TimeoutExpired,ValueError) as exc:
        raise ProductionBlocked("Real media probe failed") from exc
    videos=[x for x in data.get("streams",[]) if x.get("codec_type")=="video"]
    audios=[x for x in data.get("streams",[]) if x.get("codec_type")=="audio"]
    seconds=float(data.get("format",{}).get("duration") or 0)
    if not videos or seconds<1:
        raise ProductionBlocked("No meaningful motion-video stream")
    v=videos[0]
    if v.get("width",0)<1280 or v.get("height",0)<720:
        raise ProductionBlocked("Below minimum 720p review resolution")
    if dialogue and not audios:
        raise ProductionBlocked("Dialogue shot is missing an audio stream")
    return {"duration_s":seconds,"width":v["width"],"height":v["height"],
            "has_audio":bool(audios),"media_verified":True}


def evaluate_shot(shot:dict,bible:dict,artifact:Path,report:dict, *,
                  generator:str) -> dict:
    """Independent QA evidence is required; metadata alone is not an AI quality judge.

    The checks validate provenance, verified file bytes, immutable identities,
    disjoint evaluator, and every category threshold. External multi-modal
    visual/audio QA must generate the actual scorecard, with its own evidence.
    """
    validated=validate_shot(shot,bible)
    if not isinstance(report,dict):
        raise ProductionBlocked("Quality report required")
    if report.get("schema")!="ahos.studio.independent-shot-qa.v1":
        raise ProductionBlocked("Independent QA schema required")
    if not artifact.is_file() or artifact.stat().st_size<100000:
        raise ProductionBlocked("Real rendered media file missing/suspicious")
    expected=_sha(report.get("artifact_sha256"),"Rendered artifact")
    if _hash_file(artifact)!=expected:
        raise ProductionBlocked("Rendered artifact hash differs")
    if report.get("shot_id")!=shot["shot_id"]:
        raise ProductionBlocked("Wrong shot in evaluation")
    reviewer=report.get("reviewer")
    if not isinstance(reviewer,str) or not reviewer.strip() or reviewer==generator:
        raise ProductionBlocked("An independent reviewer is mandatory")
    if report.get("human_review_or_validated_multimodal_qa") is not True:
        raise ProductionBlocked("Real image/audio review evidence required")
    ref=_sha(report.get("review_evidence_sha256"),"Reviewer evidence")
    if not isinstance(report.get("review_evidence_path"),str) or not ref:
        raise ProductionBlocked("Reviewer proof path absent")
    review_path=Path(report["review_evidence_path"]).resolve()
    if review_path.parent!=artifact.resolve().parent:
        raise ProductionBlocked("Reviewer evidence must be part of this shot job")
    if not review_path.is_file() or _hash_file(review_path)!=ref:
        raise ProductionBlocked("Reviewer proof file/hash invalid")
    media=media_probe(artifact,dialogue=shot["kind"]=="dialogue")
    locks=report.get("identity_locks")
    if locks!={cid:{k:bible["cast"][cid][k] for k in LOCKED} for cid in validated["cast"]}:
        raise ProductionBlocked("QA examined mismatched series assets")
    dimensions=report.get("scores")
    if not isinstance(dimensions,dict) or set(dimensions)!=set(QA_DIMENSIONS):
        raise ProductionBlocked("All independent creative dimensions are mandatory")
    for name, score in dimensions.items():
        if isinstance(score,bool) or not isinstance(score,(int,float)) or not 0<=score<=1:
            raise ProductionBlocked("Malformed QA score for "+name)
    fails={name:{"score":dimensions[name],"minimum":floor}
           for name,floor in QA_FLOORS.items() if dimensions[name]<floor}
    return {"shot_id":shot["shot_id"],"status":"QA_PASS" if not fails else "REPAIR_REQUIRED",
            "passes_thresholds":not fails,"production_ready":False,
            "failures":fails,"artifact_sha256":expected,
            "reviewer":reviewer,"media":media}


REPAIR_BY_FAILURE={
    "identity":"asset_identity_and_conditioning",
    "acting":"rig_acting_animation",
    "motion":"motion_track_or_rig_animation",
    "continuity":"reference_locked_scene_repair",
    "cinematography":"lighting_camera_or_dfr",
    "story_adherence":"director_and_storyboard",
    "audio":"voice_alignment_lipsync",
    "child_safety":"director_story_revision",
    "rights":"provenance_and_licensing"
}


def plan_repair(evaluation:dict, *, attempts:int,max_attempts:int=2)->dict:
    if evaluation.get("status")=="QA_PASS":
        return {"status":"NO_REPAIR_NEEDED"}
    if evaluation.get("status")!="REPAIR_REQUIRED":
        raise ProductionBlocked("Cannot plan repair from unverified QA")
    if attempts<0 or max_attempts<0:
        raise ValueError("Invalid repair count")
    if attempts>=max_attempts:
        return {"status":"BLOCKED_NEEDS_CREATIVE_REVIEW",
                "reason":"bounded repair budget exhausted; do not auto-approve"}
    failures=evaluation["failures"]
    return {"status":"TARGETED_REPAIR","attempt":attempts+1,
            "shot_id":evaluation["shot_id"],
            "work_orders":sorted(set(REPAIR_BY_FAILURE[dim] for dim in failures)),
            "re_render_scope":"failed shot only","production_ready":False}


def main(argv=None):
    ap=argparse.ArgumentParser()
    ap.add_argument("--shot",type=Path,required=True)
    ap.add_argument("--bible",type=Path,required=True)
    ap.add_argument("--providers",type=Path,required=True)
    ap.add_argument("--region",default="EU")
    args=ap.parse_args(argv)
    registry=json.loads(args.providers.read_text(encoding="utf-8"))
    providers=registry.get("providers",registry)
    result=route_shot(json.loads(args.shot.read_text(encoding="utf-8")),
                      json.loads(args.bible.read_text(encoding="utf-8")),
                      providers,region=args.region)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result["status"]=="READY_FOR_TECHNICAL_RENDER" else 2


if __name__=="__main__":
    raise SystemExit(main())
