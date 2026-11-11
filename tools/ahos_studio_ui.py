"""Local-only AHOS story box. One prompt -> plan -> optional technical MP4."""
from __future__ import annotations
import json
import sys
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from ahos_text_to_cartoon import ROOT, run_pipeline

OUTPUT = ROOT / "deliverables" / "AHOS-TEXT-TO-CARTOON"
UI = ROOT / "studio" / "text-to-cartoon" / "index.html"
BUSY = threading.Semaphore(1)
STATE = {}
GUARD = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    def reply(self, code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        route = urlsplit(self.path).path
        if route == "/":
            body = UI.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if route == "/api/health":
            self.reply(200, {"service": "AHOS Text-to-Cartoon",
                             "bound_to": "127.0.0.1", "cost_eur": 0,
                             "production_ready": False,
                             "preview_engine": "articulated vector technical test"})
            return
        parts = route.strip("/").split("/")
        if len(parts) >= 3 and parts[:2] == ["api", "jobs"]:
            try:
                job = str(uuid.UUID(parts[2]))
            except ValueError:
                self.reply(404, {"error": "bad job id"})
                return
            with GUARD:
                value = STATE.get(job)
            if value is None:
                p = OUTPUT/job/"job.json"
                if p.exists():
                    value = json.loads(p.read_text(encoding="utf-8"))
            if not value:
                self.reply(404, {"error": "job not found"})
                return
            if len(parts) == 3:
                self.reply(200, value)
                return
            if len(parts) == 4 and parts[3] in {"technical-preview.mp4","story-plan.json","result.json","technical-qa.json"}:
                file = OUTPUT/job/parts[3]
                if not file.is_file():
                    self.reply(404, {"error": "asset not found"})
                    return
                self.send_response(200)
                self.send_header("Content-Type", "video/mp4" if file.suffix==".mp4" else "application/json")
                self.send_header("Content-Length", str(file.stat().st_size))
                self.send_header("Cache-Control","no-store")
                self.end_headers()
                with file.open("rb") as stream:
                    while True:
                        chunk = stream.read(1024 * 256)
                        if not chunk: break
                        self.wfile.write(chunk)
                return
        self.reply(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/api/jobs":
            self.reply(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 65536:
                raise ValueError("Invalid body size")
            data = json.loads(self.rfile.read(length))
            prompt = data["prompt"]
            if not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= 2000:
                raise ValueError("Hikâye 1–2000 karakter olmalı")
            duration = int(data.get("duration", 6))
            if not 3 <= duration <= 20:
                raise ValueError("Süre 3–20 saniye olmalı")
            mode = data.get("mode", "preview")
            if mode not in ("preview", "plan"):
                raise ValueError("Invalid mode")
        except (KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
            self.reply(400, {"error": str(exc)})
            return
        with GUARD:
            in_progress = sum(x["status"] in ("queued","running") for x in STATE.values())
        if in_progress >= 3:
            self.reply(429, {"error": "Üç iş zaten sırada. Yeni görev üretimi durduruldu."})
            return
        job = str(uuid.uuid4())
        initial = {"job_id":job, "status":"queued","mode":mode,
                   "duration":duration,"prompt":prompt,
                   "production_ready":False}
        output=OUTPUT/job
        output.mkdir(parents=True,exist_ok=False)
        with GUARD: STATE[job]=initial
        (output/"job.json").write_text(json.dumps(initial,ensure_ascii=False,indent=2),encoding="utf-8")
        threading.Thread(target=_worker,args=(job,),daemon=True).start()
        self.reply(202, {"job_id":job,"status":"queued",
                         "status_url":f"/api/jobs/{job}"})

    def log_message(self, fmt, *args):
        print("[studio] "+fmt%args,flush=True)


def _worker(job):
    with BUSY:
        with GUARD:
            state = STATE[job]
            state["status"] = "running"
            state = dict(state)
            STATE[job] = state
        output = OUTPUT/job
        (output/"job.json").write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding="utf-8")
        try:
            result=run_pipeline(state["prompt"],output,
                                state["duration"],plan_only=(state["mode"]=="plan"))
            state["status"]="completed" if result["state"] != "BLOCKED" else "blocked"
            state["result"]=result
        except Exception as exc:
            state["status"]="failed"
            state["error"]=str(exc)[:800]
        state["production_ready"] = False
        (output/"job.json").write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding="utf-8")
        with GUARD: STATE[job]=state


def main():
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument("--port",type=int,default=8767)
    args=ap.parse_args()
    server=ThreadingHTTPServer(("127.0.0.1",args.port), Handler)
    print(f"AHOS Studio-16 local UI: http://127.0.0.1:{args.port}",flush=True)
    server.serve_forever()


if __name__=="__main__": main()
