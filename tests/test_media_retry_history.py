import hashlib
from pathlib import Path
from test_studio_media_queue import system, worker, sample_glb, qmod_floors



def test_failed_shot_reuses_same_filename_but_preserves_old_evidence(tmp_path):
    """A failed shot can render shot.mp4/model.glb again without deleting history."""
    q,os,eid=system(tmp_path)
    maker,_=worker(q,"animator-retry")
    reviewer,_=worker(q,"independent-reviewer",role="reviewer")
    first=q.lease(maker)
    job_id=first["job_id"]
    old_bytes=sample_glb()
    old_sha=hashlib.sha256(old_bytes).hexdigest()
    q.upload(maker,job_id,"model.glb",old_sha,old_bytes,first["lease_key"])
    def manifest(digest):
        return {"schema":"ahos.media.result.v1","capability":"character_model",
                "technical_status":"PASSED","new_spend_eur":0,
                "license_status":"COMMERCIAL_REVIEWED",
                "artifacts":[{"filename":"model.glb","sha256":digest}]}
    q.complete(maker,job_id,first["lease_key"],manifest(old_sha))
    q.review_claim(reviewer)
    proof=b'{"review":"test fixture only; identity mismatch"}'
    proofsha=hashlib.sha256(proof).hexdigest()
    q.upload(reviewer,job_id,"qa.json",proofsha,proof)
    verdict={"schema":"ahos.media.review.v1","method":"independent_multimodal",
             "proof":{"filename":"qa.json","sha256":proofsha},
             "scores":{k:(0.2 if k=="identity" else 1.0) for k in qmod_floors()}}
    assert q.review(reviewer,job_id,verdict)["status"]=="QUEUED"
    with q.connect() as db:
        old=db.execute(
            "SELECT sha256,local_path FROM media_artifact_history "
            "WHERE job_id=? AND attempt=1 AND role='worker'",(job_id,)).fetchone()
        qa=db.execute(
            "SELECT sha256 FROM media_artifact_history "
            "WHERE job_id=? AND attempt=1 AND role='reviewer'",(job_id,)).fetchone()
        active=db.execute("SELECT COUNT(*) FROM media_artifacts WHERE job_id=?",(job_id,)).fetchone()[0]
    assert old["sha256"]==old_sha
    assert Path(old["local_path"]).read_bytes()==old_bytes
    assert qa["sha256"]==proofsha
    assert active==0

    retry=q.lease(maker)
    assert retry["job_id"]==job_id and retry["attempt"]==2
    updated_bytes=old_bytes+b"revision"
    updated_sha=hashlib.sha256(updated_bytes).hexdigest()
    # The SAME name as attempt one is expected to work on a corrected shot.
    q.upload(maker,job_id,"model.glb",updated_sha,updated_bytes,retry["lease_key"])
    assert q.complete(maker,job_id,retry["lease_key"],manifest(updated_sha))["status"]=="AWAITING_QA"
    again=q.review_claim(reviewer)
    assert again["job_id"]==job_id
    new_proof=b'{"review":"test fixture only; identity judged consistent"}'
    new_ph=hashlib.sha256(new_proof).hexdigest()
    q.upload(reviewer,job_id,"qa.json",new_ph,new_proof)
    verdict["proof"]["sha256"]=new_ph
    verdict["scores"]={k:1.0 for k in qmod_floors()}
    assert q.review(reviewer,job_id,verdict)["status"]=="QA_PASS"
    with q.connect() as db:
        current=db.execute(
            "SELECT sha256 FROM media_artifacts WHERE job_id=? AND role='worker' "
            "AND filename='model.glb'",(job_id,)).fetchone()
    assert current["sha256"]==updated_sha
    assert os.episode(eid)["production_ready"] is False
