"""Production dispatcher: never certify a file, invoice, or status without evidence."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from ahos_studio_dispatcher import (STAGES, _verified_artifact, capabilities,
                                    dispatch, digest, load_backends)
from ahos_text_to_cartoon import parse_story


def repo(tmp_path: Path, stages: dict | None = None) -> Path:
    path = tmp_path / "repo"
    folder = path / "studio" / "pipeline"
    folder.mkdir(parents=True)
    (folder / "production-backends.json").write_text(
        json.dumps({"schema": "ahos.production.adapters.v1",
                    "zero_new_euro_spend": True,
                    "stages": {} if stages is None else stages}),
        encoding="utf-8")
    return path


def test_no_backend_means_blocked_but_job_is_persisted(tmp_path):
    r = repo(tmp_path)
    plan = parse_story("Aden ve Kaan bahçede oynuyor", 6)
    out = tmp_path / "jobs" / "one"
    result = dispatch(plan, out, r)
    assert result["status"] == "BLOCKED"
    assert result["production_ready"] is False
    assert result["stages"][0]["stage"] == "character_model"
    assert (out / "production-dispatch.json").is_file()
    assert not (out / "technical-preview.mp4").exists()
    assert len(capabilities(r)["stages"]) == len(STAGES)


@pytest.mark.parametrize("script", [
    "../../unsafe.py", "tools/studio_backends/../other.py",
    "C:/Windows/System32/payload.py", "tools/anywhere/example.py",
])
def test_untrusted_script_never_executed(tmp_path, script):
    r = repo(tmp_path, {"character_model": {"script": script, "cost_eur": 0}})
    assert not capabilities(r)["stages"]["character_model"]["installed"]


def test_paid_backend_never_runs(tmp_path):
    r = repo(tmp_path, {"character_model":
                         {"script": "tools/studio_backends/paid.py", "cost_eur": 1}})
    path = r / "tools" / "studio_backends"
    path.mkdir(parents=True)
    (path / "paid.py").write_text("raise RuntimeError('should never execute')", encoding="utf-8")
    assert not capabilities(r)["stages"]["character_model"]["installed"]
    result = dispatch(parse_story("Aden yürüyor", 4), tmp_path / "jobs" / "x", r)
    assert result["status"] == "BLOCKED"


def test_fake_blend_is_rejected_despite_matching_hash(tmp_path):
    job = tmp_path / "job"
    job.mkdir()
    file = job / "fake.blend"
    file.write_bytes(b"NOTREAL" + b"x"*2200)
    with pytest.raises(ValueError, match="signature"):
        _verified_artifact(job, "character_model",
                           {"kind": "character_model", "path": file.name,
                            "sha256": digest(file)})


def test_path_traversal_is_rejected(tmp_path):
    job = tmp_path / "job"
    job.mkdir()
    with pytest.raises(ValueError, match="unsafe"):
        _verified_artifact(job, "voice", {"kind": "voice",
                                         "path": "../../secret.wav",
                                         "sha256": "0"*64})


def test_lipsync_requires_real_viseme_sequence(tmp_path):
    job = tmp_path / "job"
    job.mkdir()
    file = job / "mouth.json"
    file.write_text(json.dumps({"visemes":[],"version":1}), encoding="utf-8")
    with pytest.raises(ValueError, match="viseme"):
        _verified_artifact(job,"lipsync",{"kind":"lipsync",
                                         "path":file.name,"sha256":digest(file)})


def test_fake_backend_reports_failed_not_verified(tmp_path):
    r=repo(tmp_path, {"character_model":
                       {"script":"tools/studio_backends/broken.py", "cost_eur":0}})
    folder=r/"tools"/"studio_backends"
    folder.mkdir(parents=True)
    (folder/"broken.py").write_text(
        'import sys\nsys.stderr.write("model not available")\nsys.exit(5)\n',
        encoding="utf-8")
    result=dispatch(parse_story("Aden yürüyor",4), tmp_path/"jobs"/"test",r)
    assert result["stages"][0]["status"]=="BLOCKED"
    assert "exit=5" in result["stages"][0]["reason"]
    assert not result["production_ready"]
