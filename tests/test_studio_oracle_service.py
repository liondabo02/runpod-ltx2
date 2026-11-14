"""Oracle localhost-only director API and segmented local Ollama planner tests."""
import importlib.util
import io
import json
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import studio_os_cloud_writer as writer
import studio_oracle_service as cloud


def fake_root(tmp_path):
    root=tmp_path/"git"
    folder=root/"studio/reference/owner_accepted_roster_v1/characters"
    folder.mkdir(parents=True, exist_ok=True)
    (folder/"01_aden.png").write_bytes(b"canonical-aden")
    (folder/"02_kaan.png").write_bytes(b"canonical-kaan")
    (root/"studio/pipeline").mkdir(parents=True, exist_ok=True)
    (root/"studio/pipeline/production-backends.json").write_text('{"stages":{}}')
    return root


def test_private_local_api_persists_one_prompt(tmp_path,monkeypatch):
    coordinator=cloud.Coordinator(tmp_path/"state",root=fake_root(tmp_path))
    # No live model/network required in unit tests.
    monkeypatch.setattr(coordinator,"enqueue",lambda eid:None)
    server=ThreadingHTTPServer(("127.0.0.1",0),cloud.handler_factory(coordinator))
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    base=f"http://127.0.0.1:{server.server_port}"
    try:
        with urlopen(base+"/health",timeout=5) as response:
            info=json.load(response)
        assert info["production_ready"] is False
        assert info["bound_to"]=="127.0.0.1"
        with urlopen(base+"/",timeout=5) as response:
            assert b"AHOS Studio OS" in response.read()
        data=json.dumps({"prompt":"Aden ve Kaan parkta yardim ediyor.",
                          "minutes":2,"languages":["tr"]}).encode()
        req=Request(base+"/api/episodes",data=data,method="POST",
                    headers={"Content-Type":"application/json"})
        with pytest.raises(HTTPError) as denied:
            urlopen(req,timeout=5)
        assert denied.value.code==403
        req.add_header("X-AHOS-Client","studio-os")
        with urlopen(req,timeout=5) as response:
            assert response.status==202
            submitted=json.load(response)
        with urlopen(base+"/api/episodes/"+submitted["episode_id"],timeout=5) as response:
            status=json.load(response)
        assert status["production_ready"] is False
        assert status["minutes"]==2 and status["scene_count"]==2
        assert status["status"]=="PLANNED"
        assert status["task_states"]["PENDING"]==submitted["task_count"]
        reboot=cloud.Coordinator(tmp_path/"state",root=fake_root(tmp_path))
        assert reboot.status(submitted["episode_id"])["episode_id"]==submitted["episode_id"]
        assert len(reboot.stories())==1
    finally:
        server.shutdown()
        server.server_close()
        coordinator.pool.shutdown(wait=True)


def test_local_writer_batches_scenes_and_detects_new_guests(monkeypatch):
    calls=[]
    class Response:
        def __init__(self,data): self.stream=io.BytesIO(json.dumps(data).encode())
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def read(self,*args):return self.stream.read(*args)

    def fake_urlopen(request,timeout=0):
        assert request.full_url=="http://127.0.0.1:11434/api/generate"
        payload=json.loads(request.data)
        assert payload["stream"] is False and payload["format"]=="json"
        calls.append(payload)
        count=3 if len(calls)==1 else 2
        episodes=[{"location":"park","summary":"Aden Kaan ve Tavsan birlikte yardim ederek paylasmayi ogreniyor.",
                   "characters":["aden","kaan","Tavsan"],"emotional_beat":"sevinç"} for i in range(count)]
        return Response({"response":json.dumps({"scenes":episodes})})

    monkeypatch.setattr(writer.urllib.request if hasattr(writer,"urllib") else __import__("urllib").request,
                        "urlopen",fake_urlopen)
    outcome=writer.generate_outline_local("Aden ve Kaan bir tavşan bulsun.",["aden","kaan"],5)
    assert outcome["status"]=="DRAFT_UNREVIEWED"
    assert len(outcome["outline"]["scenes"])==5
    assert outcome["guest_characters_pending_assets"]==["Tavsan"]
    assert len(calls)==2
    assert not outcome["production_ready"]


def test_local_writer_refuses_invalid_output(monkeypatch):
    import urllib.request
    class Response:
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def read(self,*args):return b'{"response":"{\\"scenes\\":[]}"}'
    monkeypatch.setattr(urllib.request,"urlopen",lambda *args,**kwargs:Response())
    with pytest.raises(RuntimeError,match="incorrect scene count"):
        writer.generate_outline_local("Bir hikaye",["aden"],1)


def test_public_host_disallowed():
    with pytest.raises(SystemExit,match="Public bind"):
        cloud.main(["--host","0.0.0.0"])
