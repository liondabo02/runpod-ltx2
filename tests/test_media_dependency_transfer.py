"""A rig worker must receive only QA-passed actor models and unchanged source SHA."""
import hashlib
import io
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from studio_media_queue import QueueError
import studio_media_worker_client as client
from test_studio_media_queue import system,worker,sample_glb,qmod_floors


def test_only_reviewed_model_can_feed_rig(tmp_path):
    q,os,eid=system(tmp_path)
    maker,_=worker(q,"source-artist")
    reviewer,_=worker(q,"reviewer-artist",role="reviewer")
    rig_worker,_=worker(q,"rig-artist",cap="rig")
    model=q.lease(maker)
    data=sample_glb()
    sha=hashlib.sha256(data).hexdigest()
    q.upload(maker,model["job_id"],"actor.glb",sha,data,model["lease_key"])
    manifest={"schema":"ahos.media.result.v1","capability":"character_model",
              "technical_status":"PASSED","new_spend_eur":0,
              "license_status":"COMMERCIAL_REVIEWED",
              "artifacts":[{"filename":"actor.glb","sha256":sha}]}
    q.complete(maker,model["job_id"],model["lease_key"],manifest)
    rig=q.lease(rig_worker)
    assert rig["status"]=="NO_COMPATIBLE_WORK"

    q.review_claim(reviewer)
    proof=b'{"qa":"only synthetic review fixture"}'
    proofsha=hashlib.sha256(proof).hexdigest()
    q.upload(reviewer,model["job_id"],"review.json",proofsha,proof)
    verdict={"schema":"ahos.media.review.v1","method":"independent_multimodal",
             "proof":{"filename":"review.json","sha256":proofsha},
             "scores":{k:1.0 for k in qmod_floors()}}
    assert q.review(reviewer,model["job_id"],verdict)["status"]=="QA_PASS"

    rig=q.lease(rig_worker)
    assert rig["status"]=="LEASED"
    assert "model:aden" in rig["payload"]["dependencies"]
    refs=q.dependencies_for_worker(rig_worker,rig["job_id"])
    assert any(x["filename"]=="actor.glb" and x["sha256"]==sha for x in refs)
    path,verified_sha,nbytes=q.dependency_for_worker(
        rig_worker,rig["job_id"],"model:aden","actor.glb")
    assert path.read_bytes()==data
    assert verified_sha==sha and nbytes==len(data)
    with pytest.raises(QueueError,match="approved upstream"):
        q.dependency_for_worker(rig_worker,rig["job_id"],"model:kaan","actor.glb")
    with pytest.raises(QueueError,match="active"):
        q.dependencies_for_worker(maker,rig["job_id"])

    # Tampering after QA cannot be served to the next stage.
    path.write_bytes(b"corrupted")
    with pytest.raises(QueueError,match="modified"):
        q.dependency_for_worker(rig_worker,rig["job_id"],"model:aden","actor.glb")


def test_worker_dependency_download_checks_exact_bytes(tmp_path,monkeypatch):
    payload=b"glTF"+b"t"*300
    actual_sha=hashlib.sha256(payload).hexdigest()
    index={"schema":"ahos.media.dependencies.v1","artifacts":[
        {"task_id":"model:aden","filename":"actor.glb",
         "sha256":actual_sha,"bytes":len(payload)}]}
    called=[]
    class FakeResponse:
        def __init__(self,data,headers):self.stream=io.BytesIO(data);self.headers=headers
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def read(self,*args):return self.stream.read(*args)
    def fake_urlopen(req,timeout=0):
        called.append(req.full_url)
        if "/dependencies?" in req.full_url:
            return FakeResponse(json.dumps(index).encode(),{})
        return FakeResponse(payload,{"X-Artifact-SHA256":actual_sha})
    monkeypatch.setattr(client,"urlopen",fake_urlopen)
    result=client.download_dependencies("http://127.0.0.1:8801","token",
                                         {"cast":["aden"]},"job123",tmp_path/"job")
    assert result[0]["source_task_id"]=="model:aden"
    assert Path(result[0]["path"]).read_bytes()==payload
    assert "/api/media/dependency?" in called[-1]



def test_large_approved_movie_dependency_streams_without_64mib_cap(tmp_path,monkeypatch):
    """Transport fixture only: bytes and hashes, not a real cinematic movie."""
    data=b"ftyp"+b"m"*(client.MAX_FILE+1024)
    sha=hashlib.sha256(data).hexdigest()
    listing={"schema":"ahos.media.dependencies.v1","artifacts":[{
        "task_id":"episode01:edit","filename":"full-episode.mp4",
        "sha256":sha,"bytes":len(data)}]}
    class Reply:
        def __init__(self,content,headers):
            self.source=io.BytesIO(content)
            self.headers=headers
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def read(self,n=-1):return self.source.read(n)
    def opener(request,timeout=0):
        if "/dependencies?" in request.full_url:
            return Reply(json.dumps(listing).encode(),{})
        return Reply(data,{"X-Artifact-SHA256":sha})
    monkeypatch.setattr(client,"urlopen",opener)
    result=client.download_dependencies("http://127.0.0.1:8801","token",
                                        {"cast":["aden"]},"job-test",tmp_path/"out")
    saved=Path(result[0]["path"])
    assert saved.stat().st_size>client.MAX_FILE
    assert hashlib.sha256(saved.read_bytes()).hexdigest()==sha
