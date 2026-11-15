"""Stüdyo konsolu: ofis arayüzünden konu verip bölüm üretmeyi sağlayan iş katmanı.

Tasarım kararı:
- HTTP sunucusuna bağımlı değildir; yalnızca dosya + süreç yönetir (testleri offline).
- Her iş kendi klasöründe `status.json` + `log.txt` tutar: QUEUED→RUNNING→COMPLETED/FAILED.
- Üretim ayrı süreçte çalışır (`ahos.series_cli`), böylece ofis sayfası bloklanmaz.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

STATUS_FILE = "status.json"
LOG_FILE = "log.txt"

PRODUCE_PAGE = """<!doctype html>
<html lang="tr"><head><meta charset="utf-8"><title>AHOS Studio — Üret</title>
<style>
body{font-family:system-ui,Segoe UI,Arial;background:#0e1116;color:#e8eaf0;margin:0;padding:32px}
h1{font-size:22px;margin:0 0 18px}
.box{background:#171b23;border:1px solid #2a3040;border-radius:14px;padding:20px;max-width:720px}
label{display:block;font-size:13px;color:#9aa4b8;margin:14px 0 6px}
input,select{width:100%;padding:10px 12px;border-radius:9px;border:1px solid #2f3648;background:#0f131a;color:#e8eaf0;font-size:15px}
button{margin-top:18px;width:100%;padding:12px;border:0;border-radius:10px;background:#3d7bfd;color:#fff;font-size:16px;font-weight:600;cursor:pointer}
button:disabled{background:#2a3040;color:#8892a6;cursor:default}
.row{display:flex;gap:12px}.row>div{flex:1}
#state{margin-top:18px;font-size:13px;color:#9aa4b8;white-space:pre-wrap}
video{width:100%;margin-top:16px;border-radius:12px;display:none;background:#000}
</style></head><body>
<h1>AHOS Studio — Bölüm Üret</h1>
<div class="box">
<label for="topic">Konu</label>
<input id="topic" placeholder="Örn: Geri dönüşüm ve dostluk" autofocus>
<div class="row">
<div><label for="minutes">Süre (dk)</label><select id="minutes"><option>3</option><option>6</option><option selected>9</option><option>10</option><option>15</option></select></div>
<div><label for="language">Dil</label><select id="language"><option value="tr">Türkçe</option><option value="en">English</option><option value="de">Deutsch</option></select></div>
<div><label for="episode">Bölüm</label><input id="episode" type="number" value="1" min="1"></div>
</div>
<button id="go">ÜRET</button>
<div id="state">Hazır. Konu yazıp ÜRET'e basın.</div>
<video id="player" controls playsinline></video>
</div>
<script>
const $=(id)=>document.getElementById(id);let timer=null;
async function poll(id){const r=await fetch('/api/studio/status?id='+encodeURIComponent(id));const d=await r.json();
$('state').textContent='Durum: '+d.status+(d.line?'\\n'+d.line:'');
if(d.status==='COMPLETED'){clearInterval(timer);timer=null;$('go').disabled=false;
const v=$('player');v.src='/api/studio/video?id='+encodeURIComponent(id)+'&t='+Date.now();v.style.display='block';v.play().catch(()=>{});}
else if(d.status==='FAILED'){clearInterval(timer);timer=null;$('go').disabled=false;$('state').textContent='HATA: '+(d.error||'bilinmeyen');}}
$('go').onclick=async()=>{const topic=$('topic').value.trim();if(!topic){$('state').textContent='Konu boş olamaz.';return;}
$('go').disabled=true;$('player').style.display='none';
const r=await fetch('/api/studio/produce',{method:'POST',headers:{'Content-Type':'application/json'},
body:JSON.stringify({topic,minutes:Number($('minutes').value),language:$('language').value,episode:Number($('episode').value)})});
const d=await r.json();if(!d.id){$('state').textContent='Başlatılamadı: '+JSON.stringify(d);$('go').disabled=false;return;}
$('state').textContent='Kuyruğa alındı: '+d.id;timer=setInterval(()=>poll(d.id),2000);poll(d.id);};
</script></body></html>
"""


def jobs_root(root: str | Path | None = None) -> Path:
    """İş klasörlerinin kökü (varsayılan: repo altında studio/jobs/console)."""

    if root:
        return Path(root)
    return Path(__file__).resolve().parents[2] / "studio" / "jobs" / "console"


def _write_status(job_dir: Path, payload: dict) -> dict:
    job_dir.mkdir(parents=True, exist_ok=True)
    data = dict(payload, updated_at=time.time())
    (job_dir / STATUS_FILE).write_text(json.dumps(data, ensure_ascii=False, indent=2),
                                       encoding="utf-8")
    return data


def read_status(job_id: str, *, root: str | Path | None = None) -> dict | None:
    path = jobs_root(root) / job_id / STATUS_FILE
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _last_line(log_path: Path) -> str:
    try:
        lines = [line.strip() for line in log_path.read_text(encoding="utf-8",
                                                             errors="replace").splitlines()]
    except OSError:
        return ""
    return next((line for line in reversed(lines) if line), "")


def start_job(topic: str, *, minutes: float = 9.0, language: str = "tr",
              episode: int = 1, root: str | Path | None = None,
              out_root: str | Path | None = None, python: str | None = None,
              spawn: bool = True) -> dict:
    """Üretim işini başlatır; hemen `{id, status}` döner (sayfa bloklanmaz)."""

    topic = str(topic or "").strip()
    if not topic:
        raise ValueError("topic must not be empty")

    job_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
    job_dir = jobs_root(root) / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    out_dir = Path(out_root) if out_root else (job_dir / "dizi")

    command = [python or sys.executable, "-m", "ahos.series_cli", "--root", str(out_dir),
               "--topic", topic, "--minutes", str(float(minutes)),
               "--language", str(language), "--resolution", "1920x1080",
               "produce", "--episode", str(int(episode))]
    status = _write_status(job_dir, {
        "id": job_id, "status": "QUEUED", "topic": topic, "minutes": float(minutes),
        "language": language, "episode": int(episode), "out_dir": str(out_dir),
        "command": command,
    })

    if spawn:
        with (job_dir / LOG_FILE).open("w", encoding="utf-8") as log:
            process = subprocess.Popen(
                command, cwd=str(Path(__file__).resolve().parents[1]),
                stdout=log, stderr=subprocess.STDOUT,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        status = _write_status(job_dir, {**status, "status": "RUNNING",
                                         "pid": process.pid})
    return {"id": job_id, "status": status["status"]}


def refresh_job(job_id: str, *, root: str | Path | None = None) -> dict | None:
    """İş durumunu günceller: süreç bittiyse video var mı diye bakar."""

    job_dir = jobs_root(root) / job_id
    status = read_status(job_id, root=root)
    if status is None:
        return None
    if status.get("status") in {"COMPLETED", "FAILED"}:
        return status

    episode = int(status.get("episode") or 1)
    video = (Path(str(status.get("out_dir") or "")) / "episodes"
             / f"b{episode:02d}" / "episode.mp4")
    pid = status.get("pid")
    alive = False
    if pid:
        try:
            os.kill(int(pid), 0)
            alive = True
        except (OSError, ValueError):
            alive = False

    line = _last_line(job_dir / LOG_FILE)
    if video.is_file() and video.stat().st_size > 100_000 and not alive:
        return _write_status(job_dir, {**status, "status": "COMPLETED",
                                       "video": str(video), "line": "video hazır"})
    if not alive and status.get("status") == "RUNNING":
        return _write_status(job_dir, {**status, "status": "FAILED",
                                       "error": "süreç sonlandı, video yok", "line": line})
    return _write_status(job_dir, {**status, "line": line})


def video_path(job_id: str, *, root: str | Path | None = None) -> Path | None:
    """Tamamlanmış işin videosu (yoksa None)."""

    status = refresh_job(job_id, root=root)
    if not status or status.get("status") != "COMPLETED":
        return None
    candidate = Path(str(status.get("video") or ""))
    return candidate if candidate.is_file() else None

