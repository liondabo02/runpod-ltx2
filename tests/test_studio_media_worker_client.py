"""Worker client unit tests: local execution and no new paid cloud resources."""
import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import studio_media_worker_client as client


def example_root(tmp_path, *, valid=True):
    root=tmp_path/"repo"
    folder=root/"tools/studio_backends"
    folder.mkdir(parents=True)
    script=folder/"technical_test.py"
    script.write_text('''import argparse, pathlib,hashlib,json
p=argparse.ArgumentParser()
p.add_argument("--plan");p.add_argument("--job-dir");p.add_argument("--evidence")
a=p.parse_args()
job=pathlib.Path(a.job_dir)
data=b"glTF"+b"\\\\x00"*256
(job/"technical-test.glb").write_bytes(data)
out={"stage":"character_model","status":"PASSED","cost_eur":0,
"commercial_license_verified":True,"artifacts":[{"kind":"character_model",
"path":"technical-test.glb","sha256":hashlib.sha256(data).hexdigest()}]}
pathlib.Path(a.evidence).write_text(json.dumps(out))
'''.replace('b"\\\\x00"', 'b"\\x00"'),encoding="utf-8")
    # This is a synthetic test adapter, NOT a valid or registered production model.
    reg=root/"studio/pipeline"
    reg.mkdir(parents=True)
    reg.joinpath("production-backends.json").write_text(json.dumps({
        "stages":{"character_model":{"script":"tools/studio_backends/technical_test.py",
                                      "cost_eur":0 if valid else 4}}}))
    return root


def test_reject_remote_endpoints_and_unknown_backend(tmp_path):
    with pytest.raises(client.WorkerError,match="SSH loopback"):
        client.execute_one("http://some-public-host:8801","secret",tmp_path)
    root=example_root(tmp_path,valid=False)
    with pytest.raises(client.WorkerError,match="zero new spending"):
        client.script_for_capability("character_model",root)


def test_evidence_missing_or_tampered_is_rejected(tmp_path):
    out=tmp_path/"run"
    out.mkdir()
    evidence=out/"backend-evidence.json"
    with pytest.raises(client.WorkerError,match="no evidence"):
        client.read_evidence(evidence,"character_model",out)
    payload=b"glTF"+b"0"*256
    (out/"model.glb").write_bytes(payload)
    evidence.write_text(json.dumps({
        "stage":"character_model","status":"PASSED","cost_eur":0,
        "commercial_license_verified":True,
        "artifacts":[{"path":"model.glb","kind":"character_model","sha256":"0"*64}]}))
    with pytest.raises(client.WorkerError,match="SHA"):
        client.read_evidence(evidence,"character_model",out)


def test_worker_runs_registered_backend_and_submits_only_technical_evidence(tmp_path,monkeypatch):
    root=example_root(tmp_path)
    calls=[]
    assignment={"status":"LEASED","job_id":"99aa77bb",
                "lease_key":"example-test-lease-key",
                "payload":{"schema":"ahos.media.job.v1",
                           "capability":"character_model","cast":["aden"],
                           "production_ready":False}}
    def request_json(server,path,token,data):
        calls.append(path)
        if path.endswith("/lease"):
            return assignment
        if path.endswith("/complete"):
            assert data["result"]["technical_status"]=="PASSED"
            assert data["result"]["creative_approved"] is False
            assert data["result"]["production_ready"] is False
            assert data["result"]["artifacts"][0]["filename"]=="technical-test.glb"
            return {"status":"AWAITING_QA","production_ready":False}
        raise AssertionError("Unexpected API endpoint")
    uploads=[]
    def upload(server,token,job_id,lease_key,name,bytes_data):
        uploads.append((name,bytes_data))
        return {"filename":name,"sha256":hashlib.sha256(bytes_data).hexdigest()}
    monkeypatch.setattr(client,"request_json",request_json)
    monkeypatch.setattr(client,"upload_file",upload)
    result=client.execute_one("http://127.0.0.1:8801","fake-private-token",
                              tmp_path/"jobs",root,max_seconds=40)
    assert result["status"]=="AWAITING_QA"
    assert calls==["/api/media/lease","/api/media/complete"]
    assert uploads[0][0]=="technical-test.glb"
    assert uploads[0][1].startswith(b"glTF")


def test_no_worker_job_is_not_successful_film(tmp_path,monkeypatch):
    monkeypatch.setattr(client,"request_json",
                        lambda *args,**kwargs:{"status":"NO_COMPATIBLE_WORK"})
    result=client.execute_one("http://127.0.0.1:8801","token",tmp_path)
    assert result["status"]=="NO_COMPATIBLE_WORK"


def test_failed_backend_is_requeued_not_approved(tmp_path,monkeypatch):
    root=example_root(tmp_path,valid=False)
    assignment={"status":"LEASED","job_id":"job-1","lease_key":"lease",
                "payload":{"capability":"character_model","cast":["aden"]}}
    calls=[]
    def api(server,path,token,data):
        calls.append(path)
        return assignment if path.endswith("/lease") else {"status":"QUEUED"}
    monkeypatch.setattr(client,"request_json",api)
    result=client.execute_one("http://127.0.0.1:8801","token",tmp_path/"jobs",root)
    assert result["status"]=="FAILED"
    assert result["production_ready"] is False
    assert calls[-1]=="/api/media/fail"
