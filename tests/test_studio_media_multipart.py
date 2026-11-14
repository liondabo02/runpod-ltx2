"""Real disk-backed multipart tests: resumability, idempotency, lease isolation."""
import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from studio_media_multipart import MultipartStore,CHUNK_BYTES
from studio_media_queue import QueueError
from test_studio_media_queue import system,worker


def sample_large_glb():
    # Synthetic large transport fixture, not an actual valid animated 3D model.
    return b"glTF"+b"b"*(CHUNK_BYTES+120000)


def test_multipart_real_file_bytes_resume_and_finish(tmp_path):
    q,os,eid=system(tmp_path)
    producer,_=worker(q,"multipart-worker")
    job=q.lease(producer)
    store=MultipartStore(q)
    data=sample_large_glb()
    sha=hashlib.sha256(data).hexdigest()
    session=store.start(producer,job["job_id"],job["lease_key"],
                        "model.glb",sha,len(data))
    ident=session["upload_id"]
    assert session["chunk_limit"]==CHUNK_BYTES
    first=data[:CHUNK_BYTES]
    assert store.append(producer,ident,job["lease_key"],0,first)["received"]==CHUNK_BYTES
    assert store.append(producer,ident,job["lease_key"],0,first)["status"]=="DUPLICATE"
    with pytest.raises(QueueError,match="Out-of-order"):
        store.append(producer,ident,job["lease_key"],3,b"wrong")
    # Simulate process restart. This is the same persisted SQLite session.
    again=MultipartStore(q)
    resumed=again.start(producer,job["job_id"],job["lease_key"],
                        "model.glb",sha,len(data))
    assert resumed["status"]=="RESUME"
    assert resumed["received"]==CHUNK_BYTES
    assert again.append(producer,ident,job["lease_key"],CHUNK_BYTES,
                        data[CHUNK_BYTES:])["received"]==len(data)
    result=again.finish(producer,ident,job["lease_key"])
    assert result["status"]=="STORED"
    assert result["bytes"]==len(data)
    assert result["sha256"]==sha
    with q.connect() as db:
        stored=db.execute("SELECT local_path FROM media_artifacts WHERE job_id=? AND "
                          "filename='model.glb'",(job["job_id"],)).fetchone()
    assert Path(stored["local_path"]).read_bytes()==data
    technical={"schema":"ahos.media.result.v1","capability":"character_model",
               "technical_status":"PASSED","new_spend_eur":0,
               "license_status":"COMMERCIAL_REVIEWED",
               "artifacts":[{"filename":"model.glb","sha256":sha}]}
    assert q.complete(producer,job["job_id"],job["lease_key"],technical)["status"]=="AWAITING_QA"


def test_multipart_wrong_sha_and_other_worker_lease_rejected(tmp_path):
    q,_,_=system(tmp_path)
    maker,_=worker(q,"original-worker")
    stranger,_=worker(q,"different-worker")
    job=q.lease(maker)
    store=MultipartStore(q)
    data=sample_large_glb()
    session=store.start(maker,job["job_id"],job["lease_key"],
                        "mesh.glb","0"*64,len(data))
    upload_id=session["upload_id"]
    with pytest.raises(QueueError,match="leased"):
        store.append(stranger,upload_id,job["lease_key"],0,data[:1000])
    store.append(maker,upload_id,job["lease_key"],0,data[:CHUNK_BYTES])
    store.append(maker,upload_id,job["lease_key"],CHUNK_BYTES,data[CHUNK_BYTES:])
    with pytest.raises(QueueError,match="SHA-256 mismatch"):
        store.finish(maker,upload_id,job["lease_key"])
    assert q.status()["production_ready"] is False


def test_expired_lease_refuses_finalize(tmp_path):
    q,_,_=system(tmp_path)
    maker,_=worker(q,"expiring-worker")
    job=q.lease(maker)
    store=MultipartStore(q)
    data=b"glTF"+b"0"*200
    ident=store.start(maker,job["job_id"],job["lease_key"],
                      "small.glb",hashlib.sha256(data).hexdigest(),len(data))["upload_id"]
    store.append(maker,ident,job["lease_key"],0,data)
    with q.connect() as db:
        db.execute("UPDATE media_jobs SET lease_until=0 WHERE job_id=?",(job["job_id"],))
    with pytest.raises(QueueError,match="Lease expired"):
        store.finish(maker,ident,job["lease_key"])


def test_multipart_refuses_invalid_path_and_oversize(tmp_path):
    q,_,_=system(tmp_path)
    maker,_=worker(q,"large-worker")
    job=q.lease(maker)
    store=MultipartStore(q)
    with pytest.raises(QueueError,match="Unsafe filename"):
        store.start(maker,job["job_id"],job["lease_key"],
                    "../../server.py","a"*64,1000)
    with pytest.raises(QueueError,match="multipart size"):
        store.start(maker,job["job_id"],job["lease_key"],
                    "video.mp4","a"*64,3*1024**3)
