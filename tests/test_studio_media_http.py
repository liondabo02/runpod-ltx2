"""Integration tests for actual localhost HTTP auth and worker artifact transport."""
import hashlib
import json
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from studio_oracle_service import Coordinator, handler_factory
from studio_media_queue import FLOORS


def make_root(tmp_path):
    root=tmp_path/"repo"
    ref=root/"studio/reference/owner_accepted_roster_v1/characters"
    ref.mkdir(parents=True)
    (ref/"01_aden.png").write_bytes(b"approved-aden-reference")
    (root/"studio/pipeline").mkdir(parents=True)
    (root/"studio/pipeline/production-backends.json").write_text(
        '{"schema":"ahos.production.adapters.v1","stages":{}}')
    return root


def json_call(base,path,data=None,token=None):
    headers={"Content-Type":"application/json"}
    if token:
        headers["Authorization"]="Bearer "+token
    encoded=json.dumps(data).encode() if data is not None else None
    req=Request(base+path, data=encoded,headers=headers,method="POST" if data is not None else "GET")
    with urlopen(req,timeout=8) as response:
        return response.status,json.load(response)


def register(base,admin,worker_id,role):
    return json_call(base,"/api/media/register",{
        "worker_id":worker_id,"role":role,
        "capabilities":["character_model"] if role=="worker" else [],
        "runtime_proof_sha256":"a"*64,
        "runtime_status":"VERIFIED_RUNTIME",
        "license_status":"COMMERCIAL_REVIEWED",
        "new_spend_eur":0,"region":"EU",
    },token=admin)[1]["worker_token"]


def test_http_lease_upload_qa_and_auth(tmp_path):
    coordinator=Coordinator(tmp_path/"oracle-state",root=make_root(tmp_path))
    coordinator.enqueue=lambda episode_id:None
    engine=coordinator.engine
    eid=engine.submit("Aden is walking in the garden.",minutes=1)["episode_id"]
    with engine.connect() as db:
        for task in ("intake","canon","story","storyboard","asset_inventory"):
            db.execute("UPDATE tasks SET state='DONE_VERIFIED' WHERE episode_id=? AND task_id=?",
                       (eid,task))
        frame=(coordinator.engine.root/"studio/reference/owner_accepted_roster_v1/characters/01_aden.png").read_bytes()
        db.execute("UPDATE tasks SET result_json=? WHERE episode_id=? AND task_id='canon'",
                   (json.dumps({"locked_characters":{"aden":hashlib.sha256(frame).hexdigest()}}),eid))
    folder=tmp_path/"oracle-state/episode-artifacts"/eid
    folder.mkdir(parents=True,exist_ok=True)
    shotplan=folder/"shot-plan.json"
    shotplan.write_text(json.dumps({
        "schema":"ahos.studio-os.shotplan.v1",
        "status":"DRAFT_UNREVIEWED",
        "scenes":[{"scene_id":"scene01",
                   "plot_beat":{"summary":"Aden plays safely in the garden",
                                "characters":["aden"],"location":"garden"},
                   "planned_seconds":60}]}),encoding="utf-8")
    with engine.connect() as db:
        db.execute("UPDATE tasks SET state='DONE_DRAFT',result_json=? "
                   "WHERE episode_id=? AND task_id='storyboard'",
                   (json.dumps({"draft_path":str(shotplan),
                                "sha256":hashlib.sha256(shotplan.read_bytes()).hexdigest()}),
                    eid))
    server=ThreadingHTTPServer(("127.0.0.1",0),handler_factory(coordinator))
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    base=f"http://127.0.0.1:{server.server_port}"
    try:
        with pytest.raises(HTTPError) as denied:
            json_call(base,"/api/media/status")
        assert denied.value.code==403
        admin=coordinator.media_queue.admin_key.read_text(encoding="ascii").strip()
        code,status=json_call(base,"/api/media/status",token=admin)
        assert code==200 and status["production_ready"] is False
        wtoken=register(base,admin,"media-maker","worker")
        rtoken=register(base,admin,"media-reviewer","reviewer")
        code,leased=json_call(base,"/api/media/lease",{"seconds":120},token=wtoken)
        assert leased["status"]=="LEASED"
        assert leased["payload"]["capability"]=="character_model"
        assert leased["payload"]["production_ready"] is False
        job_id=leased["job_id"]
        lease_key=leased["lease_key"]
        body=b"glTF"+b"\x00"*256
        checksum=hashlib.sha256(body).hexdigest()
        headers={"Authorization":"Bearer "+wtoken,
                 "Content-Type":"application/octet-stream",
                 "X-AHOS-Job-ID":job_id,
                 "X-AHOS-Filename":"real-test.glb",
                 "X-AHOS-SHA256":checksum,
                 "X-AHOS-Lease-Key":lease_key}
        request=Request(base+"/api/media/artifact",data=body,headers=headers,method="PUT")
        with urlopen(request,timeout=8) as response:
            assert response.status==201
            assert json.load(response)["sha256"]==checksum
        result={"schema":"ahos.media.result.v1","capability":"character_model",
                "technical_status":"PASSED","new_spend_eur":0,
                "license_status":"COMMERCIAL_REVIEWED",
                "artifacts":[{"filename":"real-test.glb","sha256":checksum}]}
        code,completed=json_call(base,"/api/media/complete",{
            "job_id":job_id,"lease_key":lease_key,"result":result},token=wtoken)
        assert code==200 and completed["status"]=="AWAITING_QA"
        _,claimed=json_call(base,"/api/media/review-claim",{},token=rtoken)
        assert claimed["job_id"]==job_id
        request=Request(base+"/api/media/artifact?job_id="+job_id+"&filename=real-test.glb",
                        headers={"Authorization":"Bearer "+rtoken})
        with urlopen(request,timeout=8) as response:
            assert response.read()==body
            assert response.headers["X-Artifact-SHA256"]==checksum
        proof=b'{"human_frames_reviewed":8,"source": "unit test only"}'
        proofsha=hashlib.sha256(proof).hexdigest()
        h={"Authorization":"Bearer "+rtoken,
           "X-AHOS-Job-ID":job_id,"X-AHOS-Filename":"test-review.json",
           "X-AHOS-SHA256":proofsha}
        request=Request(base+"/api/media/artifact",data=proof,headers=h,method="PUT")
        with urlopen(request,timeout=8) as response:
            assert response.status==201
        verdict={
            "schema":"ahos.media.review.v1",
            "method":"human_frame_audio_review",
            "proof":{"filename":"test-review.json","sha256":proofsha},
            "scores":{k:1 for k in FLOORS}}
        _,reviewed=json_call(base,"/api/media/review",{
            "job_id":job_id,"result":verdict},token=rtoken)
        assert reviewed["status"]=="QA_PASS"
        assert reviewed["production_ready"] is False
        _,state=json_call(base,"/api/episodes/"+eid)
        assert state["production_ready"] is False
        assert state["task_states"]["DONE_VERIFIED"]>=5
        assert state["task_states"]["DONE_DRAFT"]>=1
    finally:
        server.shutdown()
        server.server_close()
        coordinator.pool.shutdown(wait=True)


def test_http_registration_needs_admin(tmp_path):
    coordinator=Coordinator(tmp_path/"state",root=make_root(tmp_path))
    server=ThreadingHTTPServer(("127.0.0.1",0),handler_factory(coordinator))
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    try:
        with pytest.raises(HTTPError) as e:
            json_call(f"http://127.0.0.1:{server.server_port}","/api/media/register",{
                "worker_id":"untrusted","role":"worker",
                "runtime_proof_sha256":"a"*64,"runtime_status":"VERIFIED_RUNTIME",
                "license_status":"COMMERCIAL_REVIEWED","region":"EU",
                "new_spend_eur":0,"capabilities":["render"]})
        assert e.value.code==403
    finally:
        server.shutdown()
        server.server_close()
        coordinator.pool.shutdown(wait=True)
