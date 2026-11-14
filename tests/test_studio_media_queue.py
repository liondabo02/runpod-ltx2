"""Media Factory queue tests: real SQLite transactions and bytes, no dummy film claims."""
import hashlib
import io
import json
import time
from pathlib import Path

import pytest

from studio_media_queue import MediaQueue, QueueError, MAX_ATTEMPTS
from ahos_studio_os import StudioOS


def repo(tmp_path):
    root=tmp_path/"repo"
    refs=root/"studio/reference/owner_accepted_roster_v1/characters"
    refs.mkdir(parents=True)
    (refs/"01_aden.png").write_bytes(b"canonical aden")
    (root/"studio/pipeline").mkdir(parents=True)
    (root/"studio/pipeline/production-backends.json").write_text('{"schema":"ahos.production.adapters.v1","stages":{}}')
    return root


def system(tmp_path):
    root=repo(tmp_path)
    os=StudioOS(tmp_path/"cloud/episodes.sqlite3",root=root)
    episode=os.submit("Aden helps a baby bird learn to share.",minutes=1)
    # In tests only: simulate independently validated director tasks, no LLM network.
    with os.connect() as db:
        for tid in ("intake","canon","story","storyboard","asset_inventory"):
            db.execute("UPDATE tasks SET state='DONE_VERIFIED' WHERE episode_id=? AND task_id=?",
                       (episode["episode_id"],tid))
    queue=MediaQueue(os,tmp_path/"cloud")
    return queue,os,episode["episode_id"]


def worker(q,name,cap="character_model",role="worker"):
    registration=q.register({
        "worker_id":name,"role":role,
        "capabilities":[cap] if role=="worker" else [],
        "runtime_proof_sha256":"a"*64,"runtime_status":"VERIFIED_RUNTIME",
        "license_status":"COMMERCIAL_REVIEWED",
        "new_spend_eur":0,"region":"EU"})
    return q.auth(registration["worker_token"]),registration


def sample_glb():
    # Synthetic bytes are used ONLY in queue unit tests and cannot certify a film.
    return b"glTF"+b"\x00"*256


def test_job_dependencies_and_no_duplicate_queue(tmp_path):
    q,os,eid=system(tmp_path)
    created=q.sync_ready()
    assert created==3
    assert q.sync_ready()==0
    status=q.status()
    assert status["jobs"]["QUEUED"]==3
    assert status["production_ready"] is False
    plan=os.episode(eid)
    states={x["task_id"]:x["state"] for x in plan["tasks"]}
    assert states["model:aden"]=="READY"
    assert states["rig:aden"]=="PENDING"


def test_registration_requires_real_proof_and_zero_spend(tmp_path):
    q,_,_=system(tmp_path)
    with pytest.raises(QueueError,match="license"):
        q.register({"worker_id":"worker1","role":"worker",
                    "capabilities":["rig"],"runtime_proof_sha256":"a"*64,
                    "runtime_status":"VERIFIED_RUNTIME","license_status":"UNKNOWN",
                    "region":"EU","new_spend_eur":0})
    with pytest.raises(QueueError,match="spending"):
        q.register({"worker_id":"worker1","role":"worker",
                    "capabilities":["rig"],"runtime_proof_sha256":"a"*64,
                    "runtime_status":"VERIFIED_RUNTIME",
                    "license_status":"COMMERCIAL_REVIEWED",
                    "region":"EU","new_spend_eur":10})
    who,reg=worker(q,"worker1")
    assert who["worker_id"]=="worker1"
    assert reg["worker_token"] not in str(q.status())
    assert not q.admin_authorized("incorrect-admin-token")
    with pytest.raises(QueueError,match="Invalid worker token"):
        q.auth("wrong-token-"*5)
    with pytest.raises(QueueError,match="already registered"):
        worker(q,"worker1")


def test_lease_heartbeat_requeue_and_old_key_rejection(tmp_path):
    q,os,_=system(tmp_path)
    a,_=worker(q,"actor1")
    b,_=worker(q,"actor2")
    first=q.lease(a,seconds=35)
    assert first["status"]=="LEASED"
    assert first["payload"]["capability"]=="character_model"
    new=q.heartbeat(a,first["job_id"],first["lease_key"],seconds=60)
    assert new["lease_until"]>time.time()
    assert q.lease(a)["status"]=="WORKER_BUSY"
    with q.connect() as db:
        db.execute("UPDATE media_jobs SET lease_until=0 WHERE job_id=?",(first["job_id"],))
    second=q.lease(b,seconds=35)
    assert second["job_id"]==first["job_id"]
    assert second["attempt"]==2
    assert second["lease_key"]!=first["lease_key"]
    with pytest.raises(QueueError):
        q.heartbeat(a,first["job_id"],first["lease_key"])
    with pytest.raises(QueueError):
        q.heartbeat(b,second["job_id"],"wrong")


def test_artifact_bytes_upload_and_independent_creative_qa(tmp_path):
    q,os,eid=system(tmp_path)
    maker,_=worker(q,"model-maker")
    reviewer,_=worker(q,"qa-editor",role="reviewer")
    job=q.lease(maker)
    data=sample_glb()
    digest=hashlib.sha256(data).hexdigest()
    with pytest.raises(QueueError,match="SHA"):
        q.upload(maker,job["job_id"],"mesh.glb","0"*64,data,job["lease_key"])
    with pytest.raises(QueueError,match="filename"):
        q.upload(maker,job["job_id"],"../mesh.glb",digest,data,job["lease_key"])
    saved=q.upload(maker,job["job_id"],"model.glb",digest,data,job["lease_key"])
    assert saved["bytes"]==len(data)
    result={
        "schema":"ahos.media.result.v1",
        "capability":"character_model",
        "technical_status":"PASSED",
        "new_spend_eur":0,
        "license_status":"COMMERCIAL_REVIEWED",
        "artifacts":[{"filename":"model.glb","sha256":digest}]}
    assert q.complete(maker,job["job_id"],job["lease_key"],result)["status"]=="AWAITING_QA"
    assert os.episode(eid)["production_ready"] is False
    claim=q.review_claim(reviewer)
    assert claim["status"]=="REVIEWING"
    assert claim["artifacts"][0]["sha256"]==digest
    path,digest_copy,nbytes=q.artifact_for_review(reviewer,job["job_id"],"model.glb")
    assert path.read_bytes()==data
    assert digest_copy==digest and nbytes==len(data)
    proof=json.dumps({"visual_review":"Independent human verified",
                      "license_evidence":"Source manifest reviewed"}).encode()
    proof_sha=hashlib.sha256(proof).hexdigest()
    q.upload(reviewer,job["job_id"],"review-v1.json",proof_sha,proof)
    review={"schema":"ahos.media.review.v1","method":"human_frame_audio_review",
            "proof":{"filename":"review-v1.json","sha256":proof_sha},
            "scores":{category:1.0 for category in qmod_floors()}}
    assert q.review(reviewer,job["job_id"],review)["status"]=="QA_PASS"
    assert os.episode(eid)["production_ready"] is False
    byid={t["task_id"]:t for t in os.episode(eid)["tasks"]}
    assert byid["model:aden"]["state"]=="DONE_VERIFIED"
    assert q.sync_ready()>=1  # independent rig task becomes runnable


def qmod_floors():
    from studio_media_queue import FLOORS
    return FLOORS


def test_self_review_or_missing_evidence_denied(tmp_path):
    q,_,_=system(tmp_path)
    maker,_=worker(q,"worker1")
    job=q.lease(maker)
    with pytest.raises(QueueError,match="Review role"):
        q.review_claim(maker)
    with pytest.raises(QueueError,match="not leased"):
        q.upload({"role":"worker","worker_id":"other"},
                 job["job_id"],"out.glb","0"*64,b"hello",job["lease_key"])
    with pytest.raises(QueueError,match="proof"):
        q.review({"role":"reviewer","worker_id":"other"},job["job_id"],
                 {"schema":"ahos.media.review.v1","method":"human_frame_audio_review"})


def test_expired_third_lease_blocks_job(tmp_path):
    q,os,eid=system(tmp_path)
    maker,_=worker(q,"actor1")
    for i in range(MAX_ATTEMPTS):
        x=q.lease(maker,seconds=35)
        assert x["status"]=="LEASED"
        with q.connect() as db:
            db.execute("UPDATE media_jobs SET lease_until=0 WHERE job_id=?",(x["job_id"],))
    x=q.lease(maker)
    # First model task exhausted, other capability-neutral queued jobs remain.
    assert x["status"]=="NO_COMPATIBLE_WORK"
    with q.connect() as db:
        state=db.execute("SELECT state FROM media_jobs WHERE job_id=?",(first_id(q,os,eid),)).fetchone()
    assert state["state"]=="BLOCKED"


def first_id(q,os,eid):
    with q.connect() as db:
        return db.execute("SELECT job_id FROM media_jobs WHERE episode_id=? AND task_id='model:aden'",(eid,)).fetchone()["job_id"]


def test_failed_qa_requeues_only_the_failed_stage(tmp_path):
    q,os,eid=system(tmp_path)
    maker,_=worker(q,"actor1")
    reviewer,_=worker(q,"qa-agent",role="reviewer")
    job=q.lease(maker)
    data=sample_glb()
    sha=hashlib.sha256(data).hexdigest()
    q.upload(maker,job["job_id"],"first.glb",sha,data,job["lease_key"])
    result={"schema":"ahos.media.result.v1","capability":"character_model",
            "technical_status":"PASSED","new_spend_eur":0,
            "license_status":"COMMERCIAL_REVIEWED",
            "artifacts":[{"filename":"first.glb","sha256":sha}]}
    q.complete(maker,job["job_id"],job["lease_key"],result)
    q.review_claim(reviewer)
    proof=b'{"qa":"identity drift"}'
    ph=hashlib.sha256(proof).hexdigest()
    q.upload(reviewer,job["job_id"],"qa-1.json",ph,proof)
    verdict={"schema":"ahos.media.review.v1","method":"independent_multimodal",
             "proof":{"filename":"qa-1.json","sha256":ph},
             "scores":{k:(0.2 if k=="identity" else 1.0) for k in qmod_floors()}}
    state=q.review(reviewer,job["job_id"],verdict)
    assert state["status"]=="QUEUED"
    assert "identity" in state["failures"]
    assert os.episode(eid)["production_ready"] is False
