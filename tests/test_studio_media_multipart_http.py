"""Real Oracle localhost HTTP multipart upload API smoke test."""
import hashlib
import json
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request,urlopen

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from studio_oracle_service import Coordinator,handler_factory
from studio_media_multipart import CHUNK_BYTES
from test_studio_media_http import make_root,json_call,register


def test_http_chunked_artifact_roundtrip(tmp_path):
    owner=Coordinator(tmp_path/"state",root=make_root(tmp_path))
    owner.enqueue=lambda episode_id:None
    os=owner.engine
    eid=os.submit("Aden saves a kite with help from Kaan.",minutes=1)["episode_id"]
    frame=(os.root/"studio/reference/owner_accepted_roster_v1/characters/01_aden.png").read_bytes()
    with os.connect() as db:
        for task_id in ("intake","canon","story","storyboard","asset_inventory"):
            db.execute("UPDATE tasks SET state='DONE_VERIFIED' WHERE episode_id=? AND task_id=?",
                       (eid,task_id))
        db.execute("UPDATE tasks SET result_json=? WHERE episode_id=? AND task_id='canon'",
                   (json.dumps({"locked_characters":{"aden":hashlib.sha256(frame).hexdigest()}}),eid))
    server=ThreadingHTTPServer(("127.0.0.1",0),handler_factory(owner))
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    url="http://127.0.0.1:"+str(server.server_port)
    try:
        admin=owner.media_queue.admin_key.read_text().strip()
        token=register(url,admin,"http-part-worker","worker")
        _,leased=json_call(url,"/api/media/lease",{"seconds":120},token=token)
        assert leased["status"]=="LEASED"
        lease=leased["lease_key"]
        jid=leased["job_id"]
        data=b"glTF"+b"p"*(CHUNK_BYTES+777)
        sha=hashlib.sha256(data).hexdigest()
        _,started=json_call(url,"/api/media/uploads/start",{
            "job_id":jid,"lease_key":lease,"filename":"actor.glb",
            "sha256":sha,"size_bytes":len(data)},token=token)
        upload=started["upload_id"]
        offset=0
        while offset<len(data):
            chunk=data[offset:offset+CHUNK_BYTES]
            request=Request(url+"/api/media/uploads/"+upload,data=chunk,method="PUT",
                            headers={"Authorization":"Bearer "+token,
                                     "X-AHOS-Lease-Key":lease,
                                     "X-AHOS-Offset":str(offset)})
            with urlopen(request,timeout=20) as response:
                assert response.status==201
                result=json.load(response)
            offset=result["received"]
        _,stored=json_call(url,"/api/media/uploads/"+upload+"/finish",{
            "job_id":jid,"lease_key":lease},token=token)
        assert stored["status"]=="STORED"
        assert stored["sha256"]==sha
        assert stored["bytes"]==len(data)
        result={"schema":"ahos.media.result.v1","capability":"character_model",
                "technical_status":"PASSED","new_spend_eur":0,
                "license_status":"COMMERCIAL_REVIEWED",
                "artifacts":[{"filename":"actor.glb","sha256":sha}]}
        _,complete=json_call(url,"/api/media/complete",{
            "job_id":jid,"lease_key":lease,"result":result},token=token)
        assert complete["status"]=="AWAITING_QA"
        assert complete["production_ready"] is False
    finally:
        server.shutdown()
        server.server_close()
        owner.pool.shutdown(wait=True)
