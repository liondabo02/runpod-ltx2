"""Live office viewer: a small local web app over the holding.

Serves one page with the rooms, the workers as avatars, their live status and
current thought, plus an input bar at the bottom: what the owner types becomes an
idea in the holding (routed to a department and split into tasks).

Standard library only; binds to 127.0.0.1 by default.
"""

from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import office
from .ideas import submit

HTML = """<!doctype html>
<html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AHOS Ofis</title>
<style>
:root{--bg:#12141c;--panel:#1b1f2b;--line:#2b3244;--ink:#e8ecf6;--muted:#98a2b8;
--ok:#3ddc97;--warn:#f6c453;--bad:#ff6b6b;--accent:#7c9cff}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.45 system-ui,Segoe UI,sans-serif;height:100vh;display:flex;flex-direction:column}
header{padding:14px 18px;border-bottom:1px solid var(--line);display:flex;gap:18px;align-items:center;flex-wrap:wrap}
header h1{font-size:17px;margin:0}
.pill{padding:3px 10px;border-radius:999px;background:var(--panel);border:1px solid var(--line);font-size:12px;color:var(--muted)}
.pill b{color:var(--ink)}
main{flex:1;overflow:auto;padding:16px;display:grid;gap:14px;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));align-content:start}
.room{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:12px;min-height:180px}
.room h2{font-size:14px;margin:0 0 2px}
.room p{margin:0 0 10px;font-size:12px;color:var(--muted)}
.workers{display:grid;grid-template-columns:repeat(auto-fill,minmax(84px,1fr));gap:10px}
.worker{position:relative;text-align:center;cursor:default}
.avatar{font-size:30px;line-height:1;filter:saturate(1.1)}
.dot{width:8px;height:8px;border-radius:50%;display:inline-block;margin-right:4px}
.working .dot{background:var(--ok)}.idle .dot{background:var(--muted)}
.coordinating .dot{background:var(--accent)}
.name{font-size:11px;color:var(--muted);display:block;margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.bubble{position:absolute;left:50%;bottom:100%;transform:translate(-50%,-4px);width:190px;
background:#0d1017;border:1px solid var(--line);border-radius:10px;padding:7px 9px;font-size:11px;
color:var(--ink);opacity:0;pointer-events:none;transition:.15s;z-index:3;text-align:left}
.worker:hover .bubble{opacity:1}
.idea{color:var(--warn)}
footer{border-top:1px solid var(--line);padding:10px 14px;display:flex;gap:10px;background:#0e1118}
input{flex:1;background:var(--panel);border:1px solid var(--line);color:var(--ink);
border-radius:10px;padding:11px 12px;font-size:14px}
button{background:var(--accent);color:#0b1020;border:0;border-radius:10px;padding:11px 18px;font-weight:700}
#msg{font-size:12px;color:var(--muted);padding:6px 14px;min-height:24px}
#ceoBox{position:fixed;right:16px;bottom:84px;width:380px;max-height:52vh;overflow:auto;
background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:12px;display:none;z-index:5}
#ceoBox h3{margin:0 0 8px;font-size:13px}
.msg{margin:6px 0;padding:8px 10px;border-radius:10px;font-size:13px}
.owner{background:#22304d}.ceo{background:#16202e;border:1px solid var(--line)}
#ceoToggle{position:fixed;right:16px;bottom:84px;z-index:6}
</style></head><body>
<header><h1>🏢 AHOS Ofis</h1>
<span class="pill">daemon <b id="dstatus">-</b></span>
<span class="pill">mod <b id="dmode">-</b></span>
<span class="pill">teslim <b id="rate">-</b></span>
<span class="pill">bekleyen fikir <b id="pending">-</b></span><span class="pill">sistem <b id="infra">-</b></span><span class="pill">bilgi <b id="know">-</b></span></header>
<main id="rooms"></main>
<div id="msg"></div>
<button id="ceoToggle">CEO</button>
<div id="ceoBox"><h3>CEO ile konuş</h3><div id="ceoLog"></div>
<div style="display:flex;gap:8px;margin-top:8px"><input id="ceoInput" placeholder="Bir şey yaz…"><button id="ceoSend">Gönder</button></div></div>
<footer><input id="idea" placeholder="Bir şey yaz: 'çocuklar için yeni bir oyun yapmak istiyorum'">
<button id="send">Gönder</button></footer>
<script>
async function refresh(){
  try{
    const r = await fetch('/api/office'); const d = await r.json();
    document.getElementById('dstatus').textContent = d.holding.daemon;
    document.getElementById('dmode').textContent = d.holding.executor || '-';
    const q = d.holding.quality || {};
    document.getElementById('rate').textContent = Math.round((q.delivery_rate||0)*100)+'%';
    document.getElementById('pending').textContent = d.holding.pending_ideas;
    const infra = d.holding.infra || {};
    document.getElementById('infra').textContent = infra.ok === undefined ? '-' : (infra.ok ? 'sağlıklı' : 'sorunlu');
    const k = d.holding.knowledge || {};
    document.getElementById('know').textContent = (k.documents||0)+' belge · '+(d.holding.lessons||0)+' ders';
    const rooms = document.getElementById('rooms'); rooms.innerHTML='';
    for(const room of d.rooms){
      const el = document.createElement('section'); el.className='room';
      const h=document.createElement('h2'); h.textContent=room.name; el.appendChild(h);
      const p=document.createElement('p'); p.textContent=room.mission||''; el.appendChild(p);
      const grid=document.createElement('div'); grid.className='workers';
      for(const w of room.workers){
        const box=document.createElement('div'); box.className='worker '+w.status;
        box.innerHTML = '<div class="avatar">'+w.avatar+'</div>'+
          '<div class="bubble"><span class="dot"></span>'+(w.thought||'çalışıyor…')+
          (w.idea?'<div class="idea">💡 '+w.idea+'</div>':'')+'</div>'+
          '<span class="name">'+w.name+'</span>';
        grid.appendChild(box);
      }
      el.appendChild(grid); rooms.appendChild(el);
    }
  }catch(e){ document.getElementById('msg').textContent='bağlantı hatası: '+e; }
}
async function sendIdea(){
  const input=document.getElementById('idea'); const text=input.value.trim(); if(!text) return;
  input.value='';
  const msg=document.getElementById('msg'); msg.textContent='gönderiliyor…';
  try{
    const r=await fetch('/api/idea',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text})});
    const d=await r.json();
    msg.textContent = d.ok ? ('yönlendirildi: '+d.department+' · '+d.tasks+' görev') : ('hata: '+(d.error||''));
    refresh();
  }catch(e){ msg.textContent='hata: '+e; }
}
function addMsg(role, text){
  const log=document.getElementById('ceoLog');
  const el=document.createElement('div'); el.className='msg '+role; el.textContent=text;
  log.appendChild(el); log.scrollTop=log.scrollHeight;
}
async function sendCeo(){
  const input=document.getElementById('ceoInput'); const text=input.value.trim(); if(!text) return;
  input.value=''; addMsg('owner', text);
  try{
    const r=await fetch('/api/ceo',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:text})});
    const d=await r.json(); addMsg('ceo', d.reply || ('hata: '+(d.error||'')));
    if(d.routed) addMsg('ceo','→ '+d.routed.department+' · '+d.tasks+' görev');
  }catch(e){ addMsg('ceo','hata: '+e); }
}
document.getElementById('send').onclick=sendIdea;
document.getElementById('idea').addEventListener('keydown',e=>{if(e.key==='Enter')sendIdea();});
document.getElementById('ceoToggle').onclick=()=>{const b=document.getElementById('ceoBox');b.style.display=b.style.display==='block'?'none':'block';};
document.getElementById('ceoSend').onclick=sendCeo;
document.getElementById('ceoInput').addEventListener('keydown',e=>{if(e.key==='Enter')sendCeo();});
refresh(); setInterval(refresh, 3000);
</script></body></html>
"""


class OfficeHandler(BaseHTTPRequestHandler):
    runtime_dir: Path
    console = None

    def log_message(self, fmt, *args):  # keep the console quiet
        return

    def _send(self, payload: bytes, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):  # noqa: N802 - stdlib naming
        if self.path.split("?")[0] in {"/", "/index.html"}:
            self._send(HTML.encode("utf-8"), "text/html; charset=utf-8")
            return
        if self.path.split("?")[0] == "/api/office":
            state = office.build(self.runtime_dir)
            self._send(
                json.dumps(state, ensure_ascii=False).encode("utf-8"),
                "application/json; charset=utf-8",
            )
            return
        if self.path.split("?")[0] == "/api/ceo/thread":
            from .ceo import thread

            self._send(
                json.dumps(thread(self.runtime_dir), ensure_ascii=False).encode("utf-8"),
                "application/json; charset=utf-8",
            )
            return
        self._send(b'{"error":"not found"}', "application/json", 404)

    def do_POST(self):  # noqa: N802
        route = self.path.split("?")[0]
        if route not in {"/api/idea", "/api/ceo"}:
            self._send(b'{"error":"not found"}', "application/json", 404)
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            if route == "/api/ceo":
                from .ceo import answer

                message = str(payload.get("message") or "").strip()
                if not message:
                    raise ValueError("boş mesaj")
                result = answer(self.runtime_dir, message)
                self._send(
                    json.dumps(result, ensure_ascii=False).encode("utf-8"),
                    "application/json; charset=utf-8",
                )
                return
            text = str(payload.get("text") or "").strip()
            if not text:
                raise ValueError("boş fikir")
            idea = submit(self.console, self.runtime_dir, text)
        except Exception as exc:  # noqa: BLE001 - report, never crash
            self._send(
                json.dumps({"ok": False, "error": str(exc)[:200]}, ensure_ascii=False).encode("utf-8"),
                "application/json; charset=utf-8",
                status=400,
            )
            return
        self._send(
            json.dumps(
                {
                    "ok": True,
                    "idea_id": idea.idea_id,
                    "department": idea.department_name,
                    "tasks": len(idea.tasks),
                },
                ensure_ascii=False,
            ).encode("utf-8"),
            "application/json; charset=utf-8",
        )


def serve(
    runtime_dir: str | Path,
    *,
    port: int = 8799,
    host: str = "127.0.0.1",
    console=None,
) -> ThreadingHTTPServer:
    runtime = Path(runtime_dir)
    handler = type(
        "BoundOfficeHandler",
        (OfficeHandler,),
        {"runtime_dir": runtime, "console": console},
    )
    server = ThreadingHTTPServer((host, port), handler)
    return server


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # pragma: no cover
        pass
    args = list(sys.argv[1:] if argv is None else argv)
    runtime = Path("runtime")
    port = 8799
    if "--runtime-dir" in args:
        position = args.index("--runtime-dir")
        runtime = Path(args[position + 1])
    if "--port" in args:
        position = args.index("--port")
        port = int(args[position + 1])
    server = serve(runtime, port=port)
    if server.RequestHandlerClass.console is None:  # lazily build the real console
        from .owner_console import build_default_console

        server.RequestHandlerClass.console = build_default_console(runtime)
    print(f"AHOS Ofis: http://127.0.0.1:{port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
