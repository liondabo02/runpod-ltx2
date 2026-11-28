#!/usr/bin/env python3
"""AHOS Sanal Ofis: tarayıcıdan komut ver, işçileri/kuyruğu izle, videoyu izle, geri bildirim ver.
Başlat: python tools\\office_server.py   ->  tarayıcıda http://localhost:8787
Yalnızca bu bilgisayardan (127.0.0.1) erişilir."""
import json, os, subprocess, sys, time, mimetypes, re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, unquote
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)
import lessons, studio_enqueue, studio_daemon
import office_live, worker_events

Q = os.path.join(ROOT, "studio", "queue"); OUT = os.path.join(ROOT, "out"); REPORTS = os.path.join(ROOT, "studio", "reports")
WORKERS = [
    ("showrunner", "Yapımcı (Showrunner)", "komutu işlere böler", True), ("director", "Yönetmen", "seri bible, bölüm planı", True),
    ("writers_room", "Senaryo Odası", "yaz-eleştir-düzelt", True), ("validator", "Senaryo Denetçisi", "süre/kural kontrolü", True),
    ("voice", "Ses + Dudak", "seslendirme, ağız şekilleri", True), ("localisation", "Dublaj (10 dil)", "çeviri + yerel ses (Kurmancî: inceleme gerekli)", True),
    ("animatic", "Animatik", "ön izleme", True), ("character", "Karakter Tasarımcı", "tasarım kilitleme", True),
    ("render", "Render (2D)", "kare üretimi + montaj", True), ("video_qa", "Video Kalite", "teknik denetim", True),
    ("music_sfx", "Müzik/Efekt", "kodla üretilen telifsiz müzik + efekt", True), ("rights", "Hak/Lisans", "kaynak lisans kaydı (hukuki tavsiye değil)", True),
    ("finance", "Finans", "bölüm başı 1 EUR sınırı denetimi", True), ("research", "Araştırma", "referans/fikir notları (web gezmez)", True),
    ("analytics", "Analiz", "teknik ölçüm (izleyici verisi yok)", True), ("distribution", "Dağıtım", "yayın paketi taslağı, yükleme yapmaz", True),
    ("task_observer", "Gözlemci", "sürtünme gözlemi -> öneri", True), ("agent_doctor", "Ajan Doktoru", "işçileri sınar, bozukları bildirir", True),
    ("score_engine", "Müzik Bestecisi", "ana tema, akor, ritim, yankı; sahneye göre skor", True),
    ("fx_layer", "Efekt Sanatçısı", "geçiş, parçacık, ışık huzmesi, duygu simgeleri", True),
    ("audio_polish", "Ses Mühendisi", "TTS sessizlik kırpma, seviye eşitleme, senkron", True),
    ("script_enrich", "Senaryo Zenginleştirici", "senaryoyu bozmadan tepki/şaka/arka plan ekler (onaya sunar)", True),
    ("standards", "Kalite Standardı Denetçisi", "2D kalite kapıları: yüz, ses, senkron, müzik, kurgu", True),
    ("software", "Yazılım Şirketi", "motorları geliştirir: eksiği bulur, düzeltir, kırmızı-yeşil testle kabul eder", True),
]

def jobs():
    res = []
    for f in sorted(os.listdir(Q)) if os.path.isdir(Q) else []:
        m = re.match(r"(.+)\.(pending|running|done|failed)\.json$", f)
        if not m: continue
        try: j = json.load(open(os.path.join(Q, f), encoding="utf-8"))
        except Exception: continue
        res.append({"id": m.group(1), "state": m.group(2), "command": j.get("command", ""), "error": j.get("error", "")})
    return res[-30:]

def videos():
    v = []
    for dp, _, fs in os.walk(OUT):
        for f in fs:
            if f.lower().endswith(".mp4"):
                p = os.path.join(dp, f); v.append((os.path.getmtime(p), os.path.relpath(p, OUT).replace("\\", "/")))
    return [{"path": p, "when": time.strftime("%d.%m %H:%M", time.localtime(t))} for t, p in sorted(v, reverse=True)[:25]]

def daemon_state():
    try:
        h = json.load(open(os.path.join(Q, "heartbeat.json")))
        alive = time.time() - h["at"] < 90
        return {"alive": alive, "state": h["state"] if alive else "kapalı"}
    except Exception:
        return {"alive": False, "state": "kapalı"}

ORDER = [("director", "director"), ("writers_room", "writers_room"), ("qa", "validator"), ("voice+lipsync", "voice"),
         ("edit(animatic)", "animatic"), ("character_model", "character"), ("render", "render"), ("qa(video)", "video_qa")]

def worker_states(busy):
    """pending/ready/active/done/failed — progress.json'dan; iş yoksa hepsi hazır."""
    if not busy: return {}
    try: pr = json.load(open(os.path.join(Q, "progress.json"), encoding="utf-8"))
    except Exception: pr = {"done": [], "failed": []}
    st, active_set = {}, False
    for step, wid in ORDER:
        if step in pr.get("failed", []): st[wid] = "failed"
        elif step in pr.get("done", []) or (step == "director" and "director" in pr.get("done", [])): st[wid] = "done"
        elif not active_set: st[wid] = "active"; active_set = True
        else: st[wid] = "waiting"
    if not pr.get("done") and not pr.get("failed"): st["showrunner"] = "active"
    else: st["showrunner"] = "done" if not active_set else "active"
    return st

def status():
    log = ""
    try: log = "".join(open(os.path.join(Q, "daemon.log"), encoding="utf-8").readlines()[-12:])
    except Exception: pass
    d = daemon_state()
    busy = d["state"].startswith("çalışıyor")
    rep = sorted(os.listdir(REPORTS))[-1] if os.path.isdir(REPORTS) and os.listdir(REPORTS) else ""
    ws = worker_states(busy)
    return {"daemon": d, "jobs": jobs(), "videos": videos(), "log": log, "latest_report": rep,
            "workers": [{"id": i, "name": n, "role": r, "connected": c, "state": ws.get(i, "off" if not c else "ready")} for i, n, r, c in WORKERS],
            "lessons": {w: [{"t": x["lesson"], "owner": x["source"] == "owner", "n": x["count"]} for x in lessons.top(w, 12)] for w in ("writer", "critic")}}

def live_status():
    d = daemon_state(); js = jobs()
    running = [j["id"] for j in js if j["state"] == "running"]
    ev = worker_events.read()
    live = office_live.derive(WORKERS, ev, running, d["alive"], time.time())
    return {"now": time.time(), "daemon": d, "jobs": js, "workers": live, "feed": ev[-60:], "videos": videos()[:5]}

def cancel_running():
    if not any(j["state"] == "running" for j in jobs()):
        return {"ok": False, "msg": "çalışan iş yok"}
    open(os.path.join(Q, "CANCEL"), "w").write("1")
    return {"ok": True, "msg": "iptal isteği gönderildi"}

_daemon = {"p": None}
def start_daemon():
    if daemon_state()["alive"]: return "zaten çalışıyor"
    try: os.remove(os.path.join(Q, "STOP"))
    except OSError: pass
    flags = 0x00000200 if os.name == "nt" else 0
    _daemon["p"] = subprocess.Popen([sys.executable, os.path.join(HERE, "studio_daemon.py")], cwd=ROOT, creationflags=flags)
    return "başlatıldı"

def stop_daemon():
    os.makedirs(Q, exist_ok=True); open(os.path.join(Q, "STOP"), "w").write("1"); return "durdurma isteği verildi (iş bitince kapanır)"

LOCAL_HOSTS = ("127.0.0.1", "localhost", "::1")

def request_allowed(host, origin, port):
    """Yalnız bu bilgisayarın kendi ofis sayfası. Host: DNS yönlendirme saldırısına, Origin: başka sitelerin komut göndermesine karşı.
    Alan adı TAM karşılaştırılır ('localhost.ornek.com' geçmez)."""
    try:
        h = urlparse("//" + (host or ""))
        if h.hostname not in LOCAL_HOSTS or (h.port or 80) != port:
            return False
        if origin is None:
            return True
        o = urlparse(origin)
        return o.scheme == "http" and o.hostname in LOCAL_HOSTS and (o.port or 80) == port
    except ValueError:
        return False

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _allowed(self):
        return request_allowed(self.headers.get("Host"), self.headers.get("Origin"), self.server.server_address[1])
    def _json(self, o, code=200):
        b = json.dumps(o, ensure_ascii=False).encode("utf-8")
        self.send_response(code); self.send_header("Content-Type", "application/json; charset=utf-8"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        if not self._allowed():
            return self.send_error(403)
        u = urlparse(self.path)
        if u.path in ("/", "/index.html", "/insan", "/canli"):
            page = {"/insan": "index_insan.html", "/canli": "index_canli.html"}.get(u.path, "index.html")
            b = open(os.path.join(ROOT, "studio", "office", page), "rb").read()
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
        elif u.path == "/api/status": self._json(status())
        elif u.path == "/api/live": self._json(live_status())
        elif u.path == "/api/report":
            st = status()["latest_report"]
            self._json({"text": open(os.path.join(REPORTS, st), encoding="utf-8").read() if st else "Henüz rapor yok."})
        elif u.path.startswith("/video/"): self.video(unquote(u.path[7:]))
        else: self.send_error(404)
    def video(self, rel):
        p = os.path.abspath(os.path.join(OUT, rel))
        if not p.startswith(os.path.abspath(OUT) + os.sep) or not os.path.isfile(p): return self.send_error(404)
        size = os.path.getsize(p); a, b = 0, size - 1; code = 200
        m = re.match(r"bytes=(\d*)-(\d*)", self.headers.get("Range", ""))
        if m and (m.group(1) or m.group(2)):
            if m.group(1): a = int(m.group(1))
            if m.group(2): b = int(m.group(2))
            if not m.group(1): a, b = size - int(m.group(2)), size - 1
            b = min(b, size - 1); code = 206
        self.send_response(code); self.send_header("Content-Type", mimetypes.guess_type(p)[0] or "video/mp4"); self.send_header("Accept-Ranges", "bytes")
        if code == 206: self.send_header("Content-Range", "bytes %d-%d/%d" % (a, b, size))
        self.send_header("Content-Length", str(b - a + 1)); self.end_headers()
        with open(p, "rb") as f:
            f.seek(a); left = b - a + 1
            while left > 0:
                d = f.read(min(65536, left))
                if not d: break
                try: self.wfile.write(d)
                except OSError: break
                left -= len(d)
    def do_POST(self):
        if not self._allowed():
            return self.send_error(403)
        n = int(self.headers.get("Content-Length") or 0)
        try: d = json.loads(self.rfile.read(n) or b"{}")
        except ValueError: return self._json({"error": "bozuk istek"}, 400)
        p = urlparse(self.path).path
        if p == "/api/ceo":
            m = str(d.get("message", "")).strip()[:2000]
            if not m: return self._json({"error": "mesaj boş"}, 400)
            s = live_status()
            self._json(office_live.ceo_reply(m, s["workers"], s["jobs"], s["daemon"]["alive"],
                       model=lambda a, c: office_live.model_reply(a, c, env=studio_daemon.llm_env())))
        elif p == "/api/cancel": self._json(cancel_running())
        elif p == "/api/command":
            c = str(d.get("command", "")).strip()
            if not c: return self._json({"error": "komut boş"}, 400)
            rs = int(d.get("render_seconds", 12))
            jid = studio_enqueue.enqueue(c, d.get("series_id") or None, int(d.get("seconds", 480)), rs)
            msg = start_daemon() if d.get("autostart", True) else ""
            self._json({"ok": True, "id": jid, "daemon": msg})
        elif p == "/api/feedback":
            w, t = d.get("worker", "writer"), str(d.get("text", "")).strip()
            if w not in ("writer", "critic") or not t: return self._json({"error": "geçersiz"}, 400)
            lessons.add("writers_room" if w == "writer" else "writers_room_critic", t, source="owner", count=5); self._json({"ok": True})
        elif p == "/api/retire":
            w = d.get("worker", "writer"); n = lessons.retire("writers_room" if w == "writer" else "writers_room_critic", str(d.get("text", "")))
            self._json({"ok": True, "removed": n})
        elif p == "/api/daemon": self._json({"ok": True, "msg": start_daemon() if d.get("do") == "start" else stop_daemon()})
        else: self.send_error(404)

def safe_console():
    """Çıktı bir dosyaya/boruya yönlendirilince Windows kod sayfası (ör. cp1252) Türkçe harfi yazamayabilir: sunucu bir mesaj yüzünden çökmez."""
    for s in (sys.stdout, sys.stderr):
        try: s.reconfigure(errors="replace")
        except Exception: pass

def main():
    safe_console()
    port = int(os.environ.get("AHOS_OFFICE_PORT", "8787")); os.makedirs(Q, exist_ok=True)
    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    print("AHOS Sanal Ofis hazır: http://localhost:%d   (kapatmak için Ctrl+C)" % port, flush=True)
    try: srv.serve_forever()
    except KeyboardInterrupt: pass

if __name__ == "__main__":
    main()
