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
#goalStrip{padding:6px 18px;border-bottom:1px solid var(--line);font-size:12px;color:var(--muted)}
#tabs{display:flex;gap:8px;padding:8px 18px;border-bottom:1px solid var(--line)}
#tabs button{background:var(--panel);color:var(--ink);border:1px solid var(--line);border-radius:999px;padding:6px 14px;cursor:pointer}
#tabs button.active{background:var(--accent);color:#0b1020;font-weight:700}
.tabPanel{display:none;padding:12px 18px}.tabPanel.active{display:block}
.tabPanel iframe{width:100%;height:70vh;border:0;border-radius:12px;background:#0b0e14}
.tabRow{padding:6px 0;border-bottom:1px solid var(--line);font-size:13px}
.tabRow b{color:var(--ink)}
#recentWrap{padding:8px 18px;border-bottom:1px solid var(--line);font-size:12px;color:var(--muted)}
#recentWrap b{color:var(--ink)}.recentItem{margin-right:14px;white-space:nowrap}
.ok{color:var(--ok)}.bad{color:var(--bad)}
#ceoBox{position:fixed;right:16px;bottom:84px;width:380px;max-height:52vh;overflow:auto;
background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:12px;display:none;z-index:5}
#ceoBox h3{margin:0 0 8px;font-size:13px}
.msg{margin:6px 0;padding:8px 10px;border-radius:10px;font-size:13px}
.owner{background:#22304d}.ceo{background:#16202e;border:1px solid var(--line)}
#ceoToggle{position:fixed;right:16px;bottom:84px;z-index:6}
</style></head><body>
<nav id="tabs"><button data-tab="office" class="active">Ofis</button><button data-tab="codex">Codex</button><button data-tab="harun">Harun AI</button><button data-tab="track">Görevler</button><button data-tab="products">Ürünler</button></nav><header><h1>🏢 AHOS Ofis</h1>
<span class="pill">daemon <b id="dstatus">-</b></span>
<span class="pill">mod <b id="dmode">-</b></span>
<span class="pill">teslim <b id="rate">-</b></span>
<span class="pill">bekleyen fikir <b id="pending">-</b></span><span class="pill">sistem <b id="infra">-</b></span><span class="pill">bilgi <b id="know">-</b></span><a href="/ofis" style="text-decoration:none;border:1px solid #27324a;border-radius:999px;padding:6px 12px;color:#eef3ff;background:#16223a">🏢 Ofis Katı</a></header>
<div id="goalStrip">hedefler: <span id="goals">-</span></div>
<div id="recentWrap">son görevler: <span id="recent">-</span></div>
<section id="tab-codex" class="tabPanel"><iframe src="http://127.0.0.1:8766/office" title="Codex paneli" loading="lazy"></iframe></section><section id="tab-harun" class="tabPanel"><div id="harunInfo"></div></section><section id="tab-track" class="tabPanel"><div id="trackList"></div></section><section id="tab-products" class="tabPanel"><div id="productList"></div></section><main id="rooms"></main>
<div id="msg"></div>
<button id="ceoToggle">CEO</button>
<div id="ceoBox"><h3>CEO ile konuş</h3><div id="ceoLog"></div>
<div style="display:flex;gap:8px;margin-top:8px"><input id="ceoInput" placeholder="Bir şey yaz…"><button id="ceoSend">Gönder</button></div></div>
<footer><input id="idea" placeholder="Bir şey yaz: 'çocuklar için yeni bir oyun yapmak istiyorum'">
<button id="send">Gönder</button></footer>
<script>
let selectedTab = 'office';
function showTab(name) {
  const allowed = ['office','codex','harun','track','products'];
  if (!allowed.includes(name)) name = 'office';
  selectedTab = name;
  document.querySelectorAll('#tabs button').forEach(b => b.classList.toggle('active', b.dataset.tab === name));
  const panels = {office:'rooms',codex:'tab-codex',harun:'tab-harun',track:'tab-track',products:'tab-products'};
  Object.keys(panels).forEach(key => {
    const el = document.getElementById(panels[key]);
    if (!el) return;
    el.classList.toggle('active', key === name);
    el.style.display = key === name ? (key === 'office' ? 'grid' : 'block') : 'none';
  });
}
document.querySelectorAll('#tabs button').forEach(b => b.onclick = () => showTab(b.dataset.tab));
function esc(value) { return String(value == null ? '' : value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
async function refresh(){
  try{
    const r = await fetch('/api/office'); const d = await r.json();
    document.getElementById('dstatus').textContent = d.holding.daemon;
    document.getElementById('dmode').textContent = d.holding.executor || '-';
    const q = d.holding.quality || {};
    const qrate = (d.holding.queue_rate != null) ? d.holding.queue_rate : (q.delivery_rate||0);
    document.getElementById('rate').textContent = Math.round(qrate*100)+'% (bugün '+Math.round((q.today_rate||0)*100)+'%)';
    document.getElementById('rate').title = 'genel ortalama / bugünkü kuyruk';
    document.getElementById('pending').textContent = d.holding.pending_ideas;
    const infra = d.holding.infra || {};
    document.getElementById('infra').textContent = infra.ok === undefined ? '-' : (infra.ok ? 'sağlıklı' : 'sorunlu');
    const k = d.holding.knowledge || {};
    document.getElementById('know').textContent = (k.documents||0)+' belge · '+(d.holding.lessons||0)+' ders';
    const goalsData = d.holding.goals || [];
    document.getElementById('goals').innerHTML = goalsData.length
      ? goalsData.map(function(g){ return '<span class="recentItem">'+esc(g.title.slice(0,40))+
        ' <b>%'+Math.round(g.progress*100)+'</b> ('+esc(g.status)+')</span>'; }).join('')
      : '<span class="bad">hedef yok</span>';
    const projects = d.holding.projects || [];
    const harun = projects.find(function(p){return p.department==='ai-platform';});
    document.getElementById('harunInfo').innerHTML = harun
      ? '<div class="tabRow"><b>'+esc(harun.name)+'</b> · '+esc(harun.path)+' · kapı: '+(harun.gate?'var':'yok')+'</div>'
      : '<div class="tabRow">Harun AI projesi kayıtlı değil</div>';
    const tracks = d.holding.tracks || [];
    document.getElementById('trackList').innerHTML = tracks.length
      ? tracks.map(function(t){
          const rows = t.tasks.map(function(x){
            const mark = x.status==='done' ? '✅' : (x.status==='blocked' ? '⛔' : (x.status==='running' ? '⏳' : '•'));
            return '<div class="tabRow">'+mark+' '+esc(x.title.slice(0,70))+' · '+esc((x.output || x.blocker || x.status))+'</div>';
          }).join('');
          return '<div class="tabRow"><b>'+esc(t.text.slice(0,60))+'</b> → '+esc(t.department_name)+
            ' · %'+Math.round(t.progress*100)+' ('+t.done+'/'+t.total+')</div>'+rows;
        }).join('')
      : '<div class="tabRow">henüz görev yok</div>';
    const products = d.holding.products || [];
    document.getElementById('productList').innerHTML = products.length
      ? products.map(function(p){return '<div class="tabRow"><b>'+esc(p.name)+'</b> · '+p.files+' dosya · '+(p.artifact_kind==='document_package'?'belge paketi · ürün QA doğrulanmadı':'medya paketi · ürün QA doğrulanmadı')+'</div>';}).join('')
      : '<div class="tabRow">henüz ürün paketi yok</div>';
    const recent = d.holding.recent || [];
    document.getElementById('recent').innerHTML = recent.slice(0,5).map(function(m){
      const cls = m.changed > 0 ? 'ok' : 'bad';
      return '<span class="recentItem"><b>'+esc(m.at)+'</b> <span class="'+cls+'">'+esc(m.status)+'</span> '+m.changed+' dosya · '+esc(m.objective.slice(0,42))+'</span>';
    }).join('') || '<span class="bad">henüz görev yok</span>';
    showTab(selectedTab);
    const rooms = document.getElementById('rooms'); rooms.innerHTML='';
    document.getElementById('msg').textContent='';
    for(const room of d.rooms){
      const el = document.createElement('section'); el.className='room';
      const h=document.createElement('h2'); h.textContent=room.name; el.appendChild(h);
      const p=document.createElement('p'); p.textContent=room.mission||''; el.appendChild(p);
      const operations = room.operations || {};
      const contract = document.createElement('p'); contract.className = 'sub';
      contract.textContent = 'Yönetici: ' + (operations.manager || 'eksik') + ' · QA: ' + (operations.qa_worker || 'eksik') + ' · ' + (operations.status === 'configured' ? 'Görev dağılımı tanımlı' : 'Düzenleme gerekli');
      el.appendChild(contract);
      if ((operations.issues || []).length) { const issue = document.createElement('p'); issue.textContent = operations.issues.join(' · '); el.appendChild(issue); }
      const grid=document.createElement('div'); grid.className='workers';
      for(const w of room.workers){
        const box=document.createElement('div'); box.className='worker '+w.status;
        box.innerHTML = '<div class="avatar">'+esc(w.avatar)+'</div>'+
          '<div class="bubble"><span class="dot"></span>'+esc(w.thought || (w.status === 'working' ? 'Doğrulanmış aktif görev' : 'Aktif görev doğrulanmadı'))+
          (w.idea?'<div class="idea">💡 '+esc(w.idea)+'</div>':'')+'</div>'+
          '<span class="name">'+esc(w.name)+'</span>';
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
    msg.textContent = d.ok ? ('yönlendirildi: '+d.department+' · '+d.tasks+' görev · takip: Görevler sekmesi') : ('hata: '+(d.error||''));
    if(d.ok){ showTab('track'); }
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
        from urllib.parse import unquote, urlsplit
        route = urlsplit(self.path).path
        render_root = (Path(self.runtime_dir) / "artifacts" / "renders").resolve()
        if route == "/api/renders":
            files = []
            if render_root.is_dir():
                for p in render_root.iterdir():
                    try:
                        if p.suffix.lower() not in {".mp4", ".png"} or p.is_symlink() or not p.is_file():
                            continue
                        if p.resolve().parent != render_root:
                            continue
                        stat = p.stat()
                        files.append({"name": p.name, "size": stat.st_size, "modified": stat.st_mtime})
                    except OSError:
                        continue
            files.sort(key=lambda f: (f["modified"], f["name"]), reverse=True)
            self._send(json.dumps(files[:10], ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
            return
        if route.startswith("/renders/"):
            name = unquote(route[len("/renders/"):])
            target = render_root / name
            if (not name or any(c in name for c in ("/", "\\", ":", "\0"))
                    or target.suffix.lower() not in {".mp4", ".png"}
                    or target.is_symlink() or target.resolve().parent != render_root):
                self._send(b"not found", "text/plain", 404)
                return
            try:
                handle = target.open("rb")
            except OSError:
                self._send(b"not found", "text/plain", 404)
                return
            with handle:
                import os, shutil
                self.send_response(200)
                self.send_header("Content-Type", "video/mp4" if target.suffix.lower() == ".mp4" else "image/png")
                self.send_header("Content-Length", str(os.fstat(handle.fileno()).st_size))
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                shutil.copyfileobj(handle, self.wfile, length=65536)
            return
        if self.path.split("?")[0] in {"/", "/index.html"}:
            self._send(HTML.encode("utf-8"), "text/html; charset=utf-8")
            return
        if self.path.split("?")[0] == "/api/roster":
            from pathlib import Path as _Path

            roster = _Path(self.runtime_dir).parent / "config" / "roster.json"
            body = roster.read_text(encoding="utf-8") if roster.exists() else "{}"
            self._send(body.encode("utf-8"), "application/json; charset=utf-8")
            return
        if self.path.split("?")[0] == "/api/conversations":
            import json as _json
            from .commune import recent as _recent

            payload = _json.dumps(_recent(self.runtime_dir, 20), ensure_ascii=False)
            self._send(payload.encode("utf-8"), "application/json; charset=utf-8")
            return
        if self.path.split("?")[0] == "/api/talk":
            import time as _time
            from urllib.parse import parse_qs as _parse_qs

            from .worker_mind import load as _load_mind
            from .worker_mind import save as _save_mind

            query = _parse_qs(self.path.split("?", 1)[1] if "?" in self.path else "")
            worker = (query.get("worker") or [""])[0].strip()
            message = (query.get("msg") or [""])[0].strip()[:500]
            department = (query.get("dept") or [""])[0].strip()
            if not worker:
                self._send(b'{"error":"worker gerekli"}', "application/json; charset=utf-8")
                return
            mind = _load_mind(self.runtime_dir, worker, department)
            model = dict(mind.self_model or {})
            strategy = model.get("strategy") or {}
            forecast = model.get("forecast") or {}
            mood = model.get("mood") or {}
            plan = model.get("plan") or []
            goal = model.get("goal") or "-"
            rate = round(mind.success_rate * 100)

            reply = (
                f"Ben {worker} ({mind.department}). Hedefim: {goal}. "
                f"Planım: {' → '.join(plan) if plan else 'henüz plan yok'}. "
                f"Başarım %{rate} ({len(mind.events)} olay), risk: {forecast.get('risk', 'bilinmiyor')}, "
                f"ruh halim: {mood.get('label', 'nötr')}. "
                f"Stratejim: en iyi eylem '{strategy.get('best_action', '-')}', "
                f"risk toleransı {strategy.get('risk_tolerance', '-')}. "
            )
            lowered = message.lower()
            if any(word in lowered for word in ("neden", "niye")):
                reply += "Sebep: geçmiş olaylarıma ve kuyruk durumuna bakarak karar veriyorum."
            elif any(word in lowered for word in ("öner", "ne yap")):
                reply += f"Önerim: önce '{plan[0] if plan else 'durum analizi'}' adımını atmalıyım."
            elif message:
                reply += "Mesajını not aldım; sonraki turda dikkate alacağım."

            mind.events.append({
                "at": _time.strftime("%Y-%m-%dT%H:%M:%S"),
                "kind": "owner_talk",
                "detail": f"sahip: {message[:160]}",
                "ok": True,
            })
            _save_mind(self.runtime_dir, mind)
            body = json.dumps({"worker": worker, "reply": reply}, ensure_ascii=False).encode("utf-8")
            self._send(body, "application/json; charset=utf-8")
            return
        if self.path.split("?")[0] == "/ofis3d":
            from .office_3d import render_html
            self._send(render_html().encode("utf-8"), "text/html; charset=utf-8")
            return

        if self.path.split("?")[0] in {"/ofis", "/floor"}:
            from .office_floor import FLOOR_HTML

            self._send(FLOOR_HTML.encode("utf-8"), "text/html; charset=utf-8")
            return
        if self.path.split("?")[0] == "/api/office":
            state = office.build(self.runtime_dir)
            self._send(
                json.dumps(state, ensure_ascii=False).encode("utf-8"),
                "application/json; charset=utf-8",
            )
            return
        if self.path.split("?")[0] == "/api/agent-office":
            # Ajan Ofisi deseni: tüm ajanlar tek ekranda + canlı akış.
            from .agent_office import snapshot

            self._send(
                json.dumps(snapshot(self.runtime_dir), ensure_ascii=False).encode("utf-8"),
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
            from .chitchat import is_chitchat, reply as chat_reply

            if is_chitchat(text):
                self._send(
                    json.dumps(
                        {"ok": True, "chat": True, "reply": chat_reply(text), "tasks": 0},
                        ensure_ascii=False,
                    ).encode("utf-8"),
                    "application/json; charset=utf-8",
                )
                return
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
