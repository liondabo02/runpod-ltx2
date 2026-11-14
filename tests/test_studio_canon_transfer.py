"""Immutable canon intake to private worker transfer tests."""
import hashlib
import io
import json
import sys
from pathlib import Path
from urllib.request import Request
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import studio_media_worker_client as client
from studio_media_queue import QueueError
from test_studio_media_queue import system,worker


def test_canon_locks_are_in_every_dependency_ready_job(tmp_path):
    q,os,eid=system(tmp_path)
    assert q.sync_ready()>=1
    maker,_=worker(q,"canon-worker")
    job=q.lease(maker)
    source=os.root/"studio/reference/owner_accepted_roster_v1/characters/01_aden.png"
    expected=hashlib.sha256(source.read_bytes()).hexdigest()
    assert job["payload"]["canonical_reference_sha256"]=={"aden":expected}
    path,sha,size=q.reference_for_worker(maker,eid,"aden")
    assert path==source and sha==expected and size==len(source.read_bytes())
    impostor,_=worker(q,"another-worker")
    with pytest.raises(QueueError,match="Active lease"):
        q.reference_for_worker(impostor,eid,"aden")
    with pytest.raises(QueueError,match="canonical"):
        q.reference_for_worker(maker,eid,"unapproved-character")


def test_canon_changed_after_approval_refuses_transfer(tmp_path):
    q,os,eid=system(tmp_path)
    maker,_=worker(q,"guarded-worker")
    q.lease(maker)
    source=os.root/"studio/reference/owner_accepted_roster_v1/characters/01_aden.png"
    source.write_bytes(b"changed source image")
    with pytest.raises(QueueError,match="changed"):
        q.reference_for_worker(maker,eid,"aden")


def test_no_canon_hash_no_media_job(tmp_path):
    q,os,eid=system(tmp_path)
    with q.connect() as db:
        db.execute("UPDATE tasks SET result_json='{}' WHERE episode_id=? AND task_id='canon'",(eid,))
    assert q.sync_ready()==0
    assert q.status()["jobs"]=={}


def test_worker_downloads_exact_canonical_png_bytes(tmp_path,monkeypatch):
    # This is only a transport fixture, not evidence of a usable actor image.
    frame=b"\x89PNG\r\n\x1a\n"+b"fixture-opaque-data-not-a-real-image"
    sha=hashlib.sha256(frame).hexdigest()
    payload={"episode_id":"episode-1","cast":["aden"],
             "canonical_reference_sha256":{"aden":sha}}
    class Reply:
        headers={"X-Reference-SHA256":sha}
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def read(self,n=-1):return frame
    calls=[]
    def fake_open(request,timeout=0):
        calls.append(request.full_url)
        assert request.headers["Authorization"]=="Bearer private-worker-token"
        return Reply()
    monkeypatch.setattr(client,"urlopen",fake_open)
    out=client.download_canon("http://127.0.0.1:8801","private-worker-token",
                              payload,tmp_path/"job")
    assert out["aden"]["sha256"]==sha
    assert Path(out["aden"]["path"]).read_bytes()==frame
    assert "episode_id=episode-1" in calls[0]


def test_worker_detects_bad_canonical_bytes(tmp_path,monkeypatch):
    frame=b"\x89PNG\r\n\x1a\n"+"not the canonical frame".encode()
    payload={"episode_id":"episode-1","cast":["aden"],
             "canonical_reference_sha256":{"aden":"a"*64}}
    class Reply:
        headers={"X-Reference-SHA256":"a"*64}
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def read(self,n=-1):return frame
    monkeypatch.setattr(client,"urlopen",lambda *args,**kwargs:Reply())
    with pytest.raises(client.WorkerError,match="does not match hash"):
        client.download_canon("http://127.0.0.1:8801","private-worker-token",
                              payload,tmp_path/"job")
