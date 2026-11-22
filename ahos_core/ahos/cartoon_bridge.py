"""Çizgi Film Stüdyosu köprüsü: 3D/2D ofis ile film hattı (tools/studio_*) arasındaki bağ.

Ofis komut verir -> studio/queue; durum ve videolar buradan okunur. Kod üretmez, para harcamaz.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(os.environ.get("AHOS_REPO_ROOT") or Path(__file__).resolve().parents[2])
QUEUE = ROOT / "studio" / "queue"
OUT = ROOT / "out"
ORDER = [("director", "Yönetmen"), ("writers_room", "Senaryo Odası"), ("qa", "Senaryo Denetçisi"),
         ("voice+lipsync", "Ses + Dudak"), ("edit(animatic)", "Animatik"), ("character_model", "Karakter"),
         ("render", "Render 2D"), ("qa(video)", "Video Kalite")]
_STATES = ("pending", "running", "done", "failed")


def _read(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def jobs(limit: int = 8) -> list[dict]:
    rows = []
    if QUEUE.is_dir():
        for p in sorted(QUEUE.iterdir()):
            m = re.match(r"(.+)\.(pending|running|done|failed)\.json$", p.name)
            j = _read(p) if m else None
            if j is not None:
                rows.append({"id": m.group(1), "state": m.group(2), "command": str(j.get("command", ""))[:140],
                             "error": str(j.get("error", ""))[:160]})
    return rows[-limit:]


def daemon_alive() -> bool:
    hb = _read(QUEUE / "heartbeat.json") or {}
    return time.time() - float(hb.get("at", 0)) < 90


def status() -> dict:
    hb = _read(QUEUE / "heartbeat.json") or {}
    js = jobs()
    busy = any(j["state"] == "running" for j in js)
    pr = _read(QUEUE / "progress.json") or {"done": [], "failed": []}
    stages, active = [], False
    for step, name in ORDER:
        if not busy:
            st = "hazır"
        elif step in pr.get("failed", []):
            st = "hata"
        elif step in pr.get("done", []):
            st = "bitti"
        elif not active:
            st, active = "çalışıyor", True
        else:
            st = "sırada"
        stages.append({"name": name, "state": st})
    last = ""
    run = [j for j in js if j["state"] == "running"]
    if run:
        try:
            lines = (QUEUE / f"{run[-1]['id']}.log").read_text(encoding="utf-8", errors="replace").strip().splitlines()
            last = lines[-1][:140] if lines else ""
        except OSError:
            pass
    return {"last_line": last, "daemon": daemon_alive(), "state": hb.get("state", "kapalı") if daemon_alive() else "kapalı",
            "jobs": js, "stages": stages}


def videos(limit: int = 10) -> list[dict]:
    found = []
    if OUT.is_dir():
        for p in OUT.rglob("*.mp4"):
            try:
                found.append((p.stat().st_mtime, p.stat().st_size, p.relative_to(OUT).as_posix()))
            except (OSError, ValueError):
                pass
    found.sort(reverse=True)
    return [{"path": r, "size": s, "modified": t} for t, s, r in found[:limit]]


def resolve_video(rel: str) -> Path | None:
    p = (OUT / rel).resolve()
    try:
        p.relative_to(OUT.resolve())
    except ValueError:
        return None
    return p if p.suffix.lower() == ".mp4" and p.is_file() and not p.is_symlink() else None


def start_daemon() -> str:
    if daemon_alive():
        return "zaten çalışıyor"
    try:
        (QUEUE / "STOP").unlink()
    except OSError:
        pass
    script = ROOT / "tools" / "studio_daemon.py"
    if not script.is_file():
        return "studio_daemon.py bulunamadı"
    flags = 0x00000200 if os.name == "nt" else 0
    QUEUE.mkdir(parents=True, exist_ok=True)
    err = open(QUEUE / "daemon.err", "ab")   # çökerse nedeni burada görünür
    py = os.environ.get("AHOS_STUDIO_PYTHON") or sys.executable
    subprocess.Popen([py, str(script)], cwd=str(ROOT), creationflags=flags,
                     stdin=subprocess.DEVNULL, stdout=err, stderr=err)
    return "başlatıldı"


def enqueue(command: str, series_id: str | None = None, render_seconds: int = 12, seconds: int = 480) -> dict:
    command = str(command).strip()[:1500]
    if not command:
        raise ValueError("komut boş")
    QUEUE.mkdir(parents=True, exist_ok=True)
    jid = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:4]
    job = {"id": jid, "command": command, "series_id": series_id or None, "seconds": int(seconds),
           "render_seconds": int(render_seconds), "state": "pending"}
    (QUEUE / f"{jid}.pending.json").write_text(json.dumps(job, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"id": jid, "daemon": start_daemon()}


def cancel() -> str:
    QUEUE.mkdir(parents=True, exist_ok=True)
    (QUEUE / "CANCEL").write_text("1", encoding="utf-8")
    return "iptal isteği verildi"
