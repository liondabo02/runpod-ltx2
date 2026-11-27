r"""Sürekli çalışan stüdyo: kuyruktaki işleri sırayla yapar, hata olursa devam eder, periyodik olarak kendini geliştirir.
Başlat: python tools\studio_daemon.py     Durdur: studio\queue\STOP dosyası oluştur veya Ctrl+C.
--once: kuyruğu bir kez boşalt ve çık."""
import argparse, json, os, subprocess, sys, time, traceback
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE); Q = os.path.join(ROOT, "studio", "queue")
import worker_events as we

def log(msg):
    line = time.strftime("%H:%M:%S ") + msg
    try:
        print(line, flush=True)
    except Exception:   # konsolsuz (arka plan) çalışmada yazdırma hatası daemon'u düşürmesin
        pass
    os.makedirs(Q, exist_ok=True)
    open(os.path.join(Q, "daemon.log"), "a", encoding="utf-8").write(line + "\n")

def heartbeat(state):
    os.makedirs(Q, exist_ok=True)
    json.dump({"at": time.time(), "state": state}, open(os.path.join(Q, "heartbeat.json"), "w"))

def llm_env():
    """Ofisten/çift tıkla başlatılınca ortam değişkeni olmaz: OmniRoute ayarını dosyadan oku (anahtar asla yazdırılmaz)."""
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"; env["PYTHONUTF8"] = "1"   # Windows cp1252 Türkçe yazdırmada çöküyordu
    env.setdefault("AHOS_LLM_BASE", "http://localhost:20128/v1")
    env.setdefault("AHOS_LLM_MODEL", "auto")
    if not env.get("AHOS_LLM_KEY"):
        path = env.get("AHOS_LLM_SETTINGS") or os.path.join(os.path.expanduser("~"), "omniroute-test", ".claude", "settings.json")
        try:
            d = json.load(open(path, encoding="utf-8"))
            key = (d.get("env") or {}).get("ANTHROPIC_AUTH_TOKEN") or d.get("ANTHROPIC_AUTH_TOKEN")
            if key:
                env["AHOS_LLM_KEY"] = key
        except Exception:
            pass
    return env


def next_job():
    fs = sorted(f for f in os.listdir(Q) if f.endswith(".pending.json")) if os.path.isdir(Q) else []
    return fs[0] if fs else None

def run_job(fname, runner=None):
    src = os.path.join(Q, fname); job = json.load(open(src, encoding="utf-8"))
    base = fname.replace(".pending.json", "")
    run_path = os.path.join(Q, base + ".running.json"); os.replace(src, run_path)
    try: os.remove(os.path.join(Q, "progress.json"))
    except OSError: pass
    we.emit("showrunner", "start", "görevi aldı: " + str(job.get("command") or job.get("render_only") or job.get("tool") or ""), job=base)
    try:
        if runner:
            res = runner(job)
        else:
            if job.get("tool"):  # genel iş: tools\<betik>.py + argümanlar (yalnız tools klasöründeki betikler)
                tool = os.path.basename(str(job["tool"]))
                cmd = [sys.executable, os.path.join(HERE, tool)] + [str(a) for a in job.get("args", [])]
            elif job.get("render_only"):
                cmd = [sys.executable, os.path.join(HERE, "render_episode.py"), "--series-id", job["series_id"],
                       "--episode", job["render_only"], "--seconds", str(job.get("seconds", 480)),
                       "--render-seconds", str(job.get("render_seconds", 12))]
            else:
                cmd = [sys.executable, os.path.join(HERE, "showrunner.py"), "--command", job["command"],
                       "--seconds", str(job.get("seconds", 480)), "--render-seconds", str(job.get("render_seconds", 12))]
                if job.get("series_id"):
                    cmd += ["--series-id", job["series_id"]]
                if job.get("script_file"):
                    cmd += ["--script-file", job["script_file"]]
            logp = os.path.join(Q, base + ".log")
            limit = float(os.environ.get("AHOS_JOB_TIMEOUT_MIN", "45")) * 60
            t0 = time.time(); cancelled = False
            with open(logp, "w", encoding="utf-8", errors="replace") as lf:
                env = llm_env(); env["AHOS_JOB_ID"] = base
                if job.get("render_only"):
                    we.emit("render", "start", "bölümün karelerini çiziyor: %s" % job["render_only"], job=base)
                proc = subprocess.Popen(cmd, env=env, stdout=lf, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
                while proc.poll() is None:
                    time.sleep(2); heartbeat("çalışıyor: " + base)
                    if os.path.exists(os.path.join(Q, "CANCEL")):
                        cancelled = True
                    if cancelled or time.time() - t0 > limit:
                        proc.kill(); proc.wait(); break
            try: os.remove(os.path.join(Q, "CANCEL"))
            except OSError: pass
            try: tail = open(logp, encoding="utf-8", errors="replace").read()[-1500:]
            except OSError: tail = ""
            rc = proc.returncode
            res = {"returncode": rc, "tail": tail}
            if cancelled:
                raise RuntimeError("iptal edildi")
            if time.time() - t0 > limit:
                raise RuntimeError("süre aşımı (%d dk)" % (limit // 60))
            if job.get("render_only"):
                ok = rc == 0 and not cancelled
                we.emit("render", "done" if ok else "failed", "render komutu bitti (çıkış kodu %s)" % rc, job=base)
            if rc != 0:
                raise RuntimeError("showrunner kodu %s: %s" % (rc, tail[-700:]))
        job["state"] = "done"; job["result"] = res; final = base + ".done.json"
    except Exception as e:
        job["state"] = "failed"; job["error"] = str(e); job["trace"] = traceback.format_exc()[-800:]; final = base + ".failed.json"
    if job["state"] == "done":
        we.emit("showrunner", "done", "görev kuyruğu bu işi tamamladı (işçi sonuçlarına ayrıca bak)", job=base)
    else:
        we.emit("showrunner", "failed", "görev tamamlanamadı: " + job.get("error", "")[:200], job=base)
    json.dump(job, open(os.path.join(Q, final), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.remove(run_path)
    return job["state"]

def recover():
    """Çöken oturumdan kalan .running işleri tekrar sıraya al."""
    for f in os.listdir(Q) if os.path.isdir(Q) else []:
        if f.endswith(".running.json"):
            os.replace(os.path.join(Q, f), os.path.join(Q, f.replace(".running.json", ".pending.json")))

def improve():
    try:
        import studio_improver
        r = studio_improver.run(); log("Gelişim turu: yeni ders %d" % len(r["added"]))
    except Exception as e:
        log("Gelişim turu hatası: %s" % e)

def main():
    p = argparse.ArgumentParser(); p.add_argument("--once", action="store_true"); p.add_argument("--poll", type=int, default=20)
    p.add_argument("--improve-every", type=int, default=3600)
    a = p.parse_args(); os.makedirs(Q, exist_ok=True); recover(); last = 0
    log("Stüdyo başladı. Durdurmak için studio\\queue\\STOP dosyası oluştur.")
    while True:
        if os.path.exists(os.path.join(Q, "STOP")):
            log("STOP görüldü, kapanıyor."); break
        j = next_job()
        if j:
            heartbeat("çalışıyor: " + j); log("İş: " + j); log("Sonuç: " + run_job(j)); continue
        if time.time() - last > a.improve_every:
            heartbeat("gelişim"); improve(); last = time.time()
        if a.once:
            break
        heartbeat("bekliyor"); time.sleep(a.poll)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Ctrl+C ile durduruldu.")
