"""Loopback API regression test; temporary output directory and no paid service."""
from __future__ import annotations

import importlib.util
import json
import sys
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[1]
TOOLS=ROOT/"tools"
sys.path.insert(0,str(TOOLS))
spec=importlib.util.spec_from_file_location("ahos_studio_ui",TOOLS/"ahos_studio_ui.py")
ui=importlib.util.module_from_spec(spec)
spec.loader.exec_module(ui)


def call(url, data=None):
    if data is None:
        with urlopen(url,timeout=5) as resp:
            return resp.status,json.load(resp)
    raw=json.dumps(data).encode()
    req=Request(url,raw,headers={"Content-Type":"application/json"},method="POST")
    with urlopen(req,timeout=5) as resp:
        return resp.status,json.load(resp)


def test_local_job_submission_and_persistence(tmp_path, monkeypatch):
    monkeypatch.setattr(ui,"OUTPUT",tmp_path)
    with ui.GUARD: ui.STATE.clear()
    server=ThreadingHTTPServer(("127.0.0.1",0),ui.Handler)
    t=threading.Thread(target=server.serve_forever,daemon=True)
    t.start()
    try:
        root=f"http://127.0.0.1:{server.server_port}"
        status,info=call(root+"/api/health")
        assert status==200 and info["production_ready"] is False
        status,queued=call(root+"/api/jobs",{"prompt":"Aden bahçede yürüyor.","duration":3,"mode":"plan"})
        assert status==202
        job=queued["job_id"]
        for _ in range(60):
            _,current=call(root+"/api/jobs/"+job)
            if current["status"] in ("completed","failed"):
                break
            time.sleep(.05)
        assert current["status"]=="completed"
        assert current["result"]["production_ready"] is False
        assert (tmp_path/job/"story-plan.json").is_file()
        assert not (tmp_path/job/"technical-preview.mp4").exists()
        _,plan=call(root+"/api/jobs/"+job+"/story-plan.json")
        assert plan["cast"]==["aden"]
        with ui.GUARD: ui.STATE.clear()
        _,persisted=call(root+"/api/jobs/"+job)
        assert persisted["status"]=="completed"
    finally:
        server.shutdown()
        server.server_close()


def test_unsupported_cast_job_is_blocked(tmp_path,monkeypatch):
    monkeypatch.setattr(ui,"OUTPUT",tmp_path)
    with ui.GUARD: ui.STATE.clear()
    server=ThreadingHTTPServer(("127.0.0.1",0),ui.Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        root=f"http://127.0.0.1:{server.server_port}"
        _,queued=call(root+"/api/jobs",{"prompt":"Davut ve Ramin evde.","mode":"preview","duration":3})
        for _ in range(60):
            _,job=call(root+"/api/jobs/"+queued["job_id"])
            if job["status"] in ("blocked","completed","failed"): break
            time.sleep(.05)
        assert job["status"]=="blocked"
        assert job["result"]["preview"] is None
        assert not job["production_ready"]
    finally:
        server.shutdown()
        server.server_close()
