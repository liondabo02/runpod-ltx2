"""AHOS Studio OS — private Oracle coordinator with durable episode queue.

Serves only 127.0.0.1; access it through an authenticated SSH tunnel.
Generates a local Ollama screenplay draft, shot/asset plan and persistent
department tasks. It DOES NOT yet produce a finished movie or spend GPU money.
"""
from __future__ import annotations
import argparse
import json
import os
import sqlite3
import sys
import threading
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from ahos_studio_os import StudioOS

DEFAULT_STATE = Path.home() / ".local" / "share" / "ahos-studio-os"
MAX_CONTENT = 12000

PAGE = r"""<!doctype html><html lang="tr"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AHOS Studio OS — Oracle</title>
<style>body{font:16px system-ui;color:#e7eefb;background:#0e1422;max-width:850px;margin:50px auto;padding:20px}
textarea{width:100%;height:170px;background:#141d2c;color:#fff;border:1px solid #43516a;border-radius:13px;padding:15px;box-sizing:border-box;font:16px system-ui}
button{background:#63d2ca;color:#08151b;border:0;border-radius:12px;font-weight:700;padding:14px 20px;cursor:pointer}
select{background:#25354c;color:white;padding:10px;border:0;border-radius:9px}
section{background:#161f30;border:1px solid #344053;border-radius:14px;padding:22px;margin:24px 0}
small{color:#9aaecb}pre{white-space:pre-wrap;word-wrap:break-word;color:#b4d6ed}
</style>
<h1>AHOS Studio OS <small>Oracle</small></h1>
<p>Hikâyeyi yaz. Yapay zekâ yönetmeni senaryo ve sahne planını hazırlasın, iş emirlerini departmanlara dağıtsın.</p>
<section><textarea id="prompt">Aden ve Kaan ormanda kaybolan küçük bir tavşana yardım ederken paylaşmanın önemini öğrensin. Eğlenceli ve şefkatli bir hikâye oluştur.</textarea>
<p><label>Süre <select id="minutes"><option>1</option><option>3</option><option selected>8</option></select> dakika</label>
&nbsp; <label>Dil <select id="languages"><option value="tr">Türkçe</option><option value="tr,de">Türkçe + Almanca</option></select></label></p>
<button id="start">Üretim işini başlat</button></section>
<section><h2>Durum</h2><p id="state">Hazır</p><pre id="details"></pre><p id="link"></p>
<small>Mevcut altyapı senaryo planı ve görevleri üretir. Profesyonel sinematik video, ses, rig ve QA işçileri henüz tamamlanmadı. Hazır değilse gerçek engel görüntülenir.</small></section>
<script>
const $=id=>document.getElementById(id);
$('start').onclick=async()=>{
 $('start').disabled=true;$('state').textContent='İş kuyruğa yazılıyor...';
 try{
  const response=await fetch('/api/episodes',{method:'POST',headers:{'Content-Type':'application/json','X-AHOS-Client':'studio-os'},
    body:JSON.stringify({prompt:$('prompt').value,minutes:Number($('minutes').value),languages:$('languages').value.split(',')})});
  const data=await response.json();if(!response.ok)throw Error(data.error||'Gönderilemedi');
  let id=data.episode_id;$('link').textContent='Bölüm ID: '+id;
  for(let n=0;n<190;n++){
   let state=await (await fetch('/api/episodes/'+id)).json();
   $('state').textContent=state.status;
   $('details').textContent='Sahne: '+state.scene_count+'  Karakter: '+state.cast.join(', ')+
    '\nGörev durumları: '+JSON.stringify(state.task_states,null,2)+'\nFilm tamamlandı: '+state.production_ready+
    '\nEngeller: '+state.blockers.slice(0,10).map(x=>x.task+' / '+x.reason).join('\n');
   if(state.status==='WAITING_CAPABILITIES'||state.status==='FAILED')break;
   await new Promise(r=>setTimeout(r,3000));
  }
 }catch(e){$('state').textContent='Hata: '+String(e)}
 $('start').disabled=false;
};
</script></html>"""


class Coordinator:
    def __init__(self, state_dir: Path, *, root: Path = ROOT):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.engine = StudioOS(self.state_dir / "episodes.sqlite3", root=root)
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="studio-os")
        self._running = set()
        self._lock = threading.Lock()

    def enqueue(self, episode_id: str):
        with self._lock:
            if episode_id in self._running:
                return
            self._running.add(episode_id)
        self.pool.submit(self._advance, episode_id)

    def _advance(self, episode_id: str):
        try:
            for _ in range(8):
                update = self.engine.tick(episode_id, max_steps=50,
                                          use_existing_oracle=True)
                if not update["steps"]:
                    break
        except Exception as exc:
            print("AHOS director error:", type(exc).__name__, str(exc)[:200], flush=True)
            # The task state remains persisted in SQLite for inspection/retry.
        finally:
            with self._lock:
                self._running.discard(episode_id)

    def resume(self):
        with self.engine.connect() as db:
            rows = db.execute("SELECT id FROM episodes WHERE status IN "
                              "('PLANNED','IN_PROGRESS') ORDER BY created_at").fetchall()
        for row in rows:
            self.enqueue(row["id"])

    def status(self, episode_id: str) -> dict:
        data = self.engine.episode(episode_id)
        counts = dict(Counter(x["state"] for x in data["tasks"]))
        blockers = [{"task":x["task_id"],
                     "reason":x["result"].get("reason","not yet qualified")}
                    for x in data["tasks"] if x["state"]=="WAITING_PROVIDER"]
        return {"episode_id":episode_id,"series_id":data["series_id"],
                "status":data["status"],"minutes":data["minutes"],
                "scene_count":data["scene_count"],"cast":data["cast"],
                "languages":data["languages"],"task_states":counts,
                "blockers":blockers,
                "production_ready":False,
                "cloud_director_ready":True,
                "finished_movie":False}

    def stories(self, limit=30) -> list:
        with self.engine.connect() as db:
            return [dict(x) for x in db.execute(
                "SELECT id,created_at,status FROM episodes ORDER BY created_at DESC LIMIT ?",
                (limit,)).fetchall()]


def handler_factory(coordinator: Coordinator):
    class Handler(BaseHTTPRequestHandler):
        def reply(self, status, value):
            body = json.dumps(value, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type","application/json; charset=utf-8")
            self.send_header("Content-Length",str(len(body)))
            self.send_header("Cache-Control","no-store")
            self.send_header("X-Content-Type-Options","nosniff")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            route = urlsplit(self.path).path
            if route=="/":
                body=PAGE.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type","text/html; charset=utf-8")
                self.send_header("Content-Length",str(len(body)))
                self.send_header("X-Content-Type-Options","nosniff")
                self.end_headers()
                self.wfile.write(body)
            elif route=="/health":
                self.reply(200,{"service":"AHOS Studio OS Oracle",
                                "bound_to":"127.0.0.1",
                                "database":"SQLite WAL on server disk",
                                "cloud_director_ready":True,
                                "gpu_film_ready":False,
                                "production_ready":False})
            elif route=="/api/episodes":
                self.reply(200,{"episodes":coordinator.stories()})
            elif route.startswith("/api/episodes/"):
                try:
                    eid=str(uuid.UUID(route.rsplit("/",1)[-1]))
                    self.reply(200,coordinator.status(eid))
                except (ValueError,KeyError):
                    self.reply(404,{"error":"unknown episode"})
            else:
                self.reply(404,{"error":"not found"})

        def do_POST(self):
            if self.path!="/api/episodes":
                self.reply(404,{"error":"not found"})
                return
            if self.headers.get("X-AHOS-Client")!="studio-os":
                self.reply(403,{"error":"missing owner client header"})
                return
            try:
                length=int(self.headers.get("Content-Length","0"))
                if not 0<length<=MAX_CONTENT:
                    raise ValueError("invalid request length")
                data=json.loads(self.rfile.read(length))
                if not isinstance(data,dict):
                    raise ValueError("body must be object")
                languages=data.get("languages",["tr"])
                if not isinstance(languages,list) or len(languages)>3:
                    raise ValueError("languages must be list of up to 3")
                created=coordinator.engine.submit(
                    data["prompt"], minutes=data.get("minutes",8),
                    languages=tuple(languages),series_id=data.get("series_id","AHOS-FAMILY"))
            except (KeyError,ValueError,TypeError,RuntimeError) as exc:
                self.reply(400,{"error":str(exc)})
                return
            coordinator.enqueue(created["episode_id"])
            self.reply(202,created)

        def log_message(self,fmt,*args):
            print("studio-cloud: "+fmt%args,flush=True)

    return Handler


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--host",default="127.0.0.1")
    p.add_argument("--port",type=int,default=8799)
    p.add_argument("--state-dir",type=Path,default=DEFAULT_STATE)
    args=p.parse_args(argv)
    if args.host!="127.0.0.1":
        raise SystemExit("Public bind is prohibited; access through an authenticated SSH tunnel")
    os.environ["AHOS_STUDIO_ORACLE_LOCAL"]="1"
    coord=Coordinator(args.state_dir)
    coord.resume()
    server=ThreadingHTTPServer((args.host,args.port),handler_factory(coord))
    print(f"AHOS Studio OS Oracle loopback 127.0.0.1:{args.port}",flush=True)
    server.serve_forever()


if __name__=="__main__":
    main()
