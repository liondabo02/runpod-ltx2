"""Fail-closed checks for the real LTX-2.5 shot worker, no model downloads."""
import importlib.util
import hashlib
import json
from pathlib import Path
from unittest.mock import patch
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("ltx25_shot_worker",ROOT/"tools"/"ltx25_shot_worker.py")
worker=importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


def setup_shot(tmp_path):
    root=tmp_path/"repo"
    img=root/"studio/frames/frame.png"
    img.parent.mkdir(parents=True)
    img.write_bytes(b"TEST: not a real usable reference")
    plan={
        "schema":"ahos.studio.ltx25.shot.v1",
        "model":"ltx-2.5",
        "shot_prompt":"An age-appropriate animated story scene with a consistent cast and camera, smooth motions in a garden.",
        "reference_frame":{"path":"studio/frames/frame.png",
                           "sha256":hashlib.sha256(img.read_bytes()).hexdigest()},
        "license_status":"SOURCE_RIGHTS_REVIEWED",
        "frames":121,"fps":24,"width":1280,"height":720,
    }
    p=root/"studio/plan.json"
    p.write_text(json.dumps(plan),encoding="utf-8")
    return root,p,plan,img


def test_locked_reference_roundtrip(tmp_path):
    root,p,plan,img=setup_shot(tmp_path)
    loaded,source=worker.load_shot(p,root)
    assert source==img
    assert loaded["frames"]==121


def test_changed_reference_rejected(tmp_path):
    root,p,plan,img=setup_shot(tmp_path)
    img.write_bytes(b"character face was silently replaced")
    with pytest.raises(ValueError,match="hash mismatch"):
        worker.load_shot(p,root)


def test_invalid_license_rejected(tmp_path):
    root,p,plan,img=setup_shot(tmp_path)
    plan["license_status"]="UNKNOWN"
    p.write_text(json.dumps(plan),encoding="utf-8")
    with pytest.raises(ValueError,match="rights"):
        worker.load_shot(p,root)


def test_incompatible_frame_count_rejected(tmp_path):
    root,p,plan,img=setup_shot(tmp_path)
    plan["frames"]=120
    p.write_text(json.dumps(plan),encoding="utf-8")
    with pytest.raises(ValueError,match="multiple of 8"):
        worker.load_shot(p,root)


def test_path_traversal_rejected(tmp_path):
    root,p,plan,img=setup_shot(tmp_path)
    plan["reference_frame"]["path"]="../../secret.png"
    p.write_text(json.dumps(plan),encoding="utf-8")
    with pytest.raises(ValueError,match="Path traversal"):
        worker.load_shot(p,root)


def test_missing_model_fails_preflight(tmp_path):
    root,p,plan,img=setup_shot(tmp_path)
    check=worker.preflight({"ltx_repo":str(tmp_path/"not-installed"),
                            "model_dir":str(tmp_path/"not-downloaded"),
                            "provider":"existing-owned-gpu",
                            "new_spend_limit_eur":0,"license_terms_accepted":True},
                           plan,img)
    assert check["ready_for_execution"] is False
    assert check["professional_quality_verified"] is False
    assert any("model" in reason.lower() for reason in check["missing"])


def test_unapproved_gpu_never_executes(tmp_path,monkeypatch):
    root,p,plan,img=setup_shot(tmp_path)
    monkeypatch.setattr(worker,"preflight",lambda *args,**kwargs:{"ready_for_execution":True,"missing":[]})
    monkeypatch.delenv("AHOS_EXISTING_GPU_AUTHORIZED",raising=False)
    with patch.object(worker.subprocess,"run") as invoke:
        with pytest.raises(RuntimeError,match="authorization"):
            worker.execute(plan,img,{"ltx_repo":str(tmp_path),"model_dir":str(tmp_path)},
                           tmp_path/"out",permitted=False)
        invoke.assert_not_called()


def test_disallows_fake_video_without_sound(tmp_path):
    target=tmp_path/"fake.mp4"
    target.write_bytes(b"0"*150000)
    output={"format":{"duration":"5.00"},"streams":[{"codec_type":"video","width":1920,"height":1080}]}
    class FakeResult:
        stdout=json.dumps(output)
    with patch.object(worker.shutil,"which",return_value="/usr/bin/ffprobe"),\
         patch.object(worker.subprocess,"run",return_value=FakeResult()):
        with pytest.raises(RuntimeError,match="video \\+ audio"):
            worker.media_proof(target)
