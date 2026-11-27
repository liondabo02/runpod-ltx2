"""Kanıtlı çalıştırma: görev kaydından (job_ledger) talep al, komutu çalıştır, makine/kaynak sürümü/komut/çıkış kodu/ham çıktı/tarihi tek JSON'a yaz.
Kullanım: cloud_evidence.py <makine_etiketi> <iş_kimliği> <çıktı.json> -- <komut...>   (Parola/anahtar yazılmaz; yalnız izinli ortam bilgisi)"""
import datetime, json, os, platform, shutil, subprocess, sys
sys.path.insert(0, os.path.dirname(__file__))
import job_ledger, dev_cmd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def machine_info():
    mem = None
    try:
        for ln in open("/proc/meminfo"):
            if ln.startswith("MemTotal"):
                mem = int(ln.split()[1]) // 1024
    except OSError:
        pass
    du = shutil.disk_usage(os.environ.get("AHOS_SCRATCH", "/tmp"))   # gerçek çalışma diski (ROOT bir ağ bağlantısı olabilir)
    gpu = bool(shutil.which("nvidia-smi"))
    return {"platform": platform.platform(), "python": platform.python_version(), "cpu_count": os.cpu_count(), "ram_mb": mem,
            "disk_free_gb": round(du.free / 1e9, 1), "disk_total_gb": round(du.total / 1e9, 1), "gpu": gpu, "cost_eur": 0}


def _run_with_heartbeat(cmd, job, label, token):
    """Komut sürerken nabız yaz. Sahiplik kaybedilirse (iş devralınmış) süreç durdurulur: aynı iş iki yerde sürmez."""
    p = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    try:
        while True:
            try:
                stdout, stderr = p.communicate(timeout=job_ledger.TTL / 4)
                return p.returncode, stdout, stderr, job_ledger.heartbeat(ROOT, job, label, token=token)
            except subprocess.TimeoutExpired:
                if not job_ledger.heartbeat(ROOT, job, label, token=token):
                    p.kill(); stdout, stderr = p.communicate()
                    return p.returncode, stdout, stderr, False
    finally:
        if p.poll() is None:
            p.kill(); p.wait()


def main(argv=None):
    a = sys.argv[1:] if argv is None else list(argv); i = a.index("--"); label, job, out = a[0], a[1], a[2]; cmd = a[i + 1:]
    sh = dev_cmd.src_hash(ROOT)
    c = job_ledger.claim(ROOT, job, label, sh)
    if not c["ok"] or c["action"] == "DONE":      # 'out' dosyasına DOKUNMA: doğrulanmış kanıt ya da çalışan sahibin dosyası olabilir
        print(json.dumps({"job": job, "machine": label, "claim": c}, ensure_ascii=False)); return 0 if c["ok"] else 4
    token = c["token"]
    rec = {"job": job, "machine": label, "claim": {k: v for k, v in c.items() if k != "token"}, "source_sha256": sh, "command": cmd, "date": datetime.datetime.now().isoformat(timespec="seconds"), "info": machine_info()}
    try:
        code, stdout, stderr, owned = _run_with_heartbeat(cmd, job, label, token)
    except BaseException as exc:
        job_ledger.fail(ROOT, job, label, "çalıştırılamadı: " + type(exc).__name__, token=token); raise
    if not owned:
        print(json.dumps({"job": job, "machine": label, "error": "SAHIPLIK_KAYBEDILDI", "exit_code": code}, ensure_ascii=False)); return 5
    rec.update(exit_code=code, raw_tail=(stdout or "")[-1500:] + (stderr or "")[-500:])
    with open(out, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
    if code == 0:
        recorded = job_ledger.complete(ROOT, job, label, out, token=token)
    else:
        recorded = job_ledger.fail(ROOT, job, label, "exit %d" % code, token=token)
    if not recorded:
        print(json.dumps({"job": job, "machine": label, "error": "SAHIPLIK_KAYBEDILDI", "exit_code": code}, ensure_ascii=False)); return 5
    print(json.dumps({k: rec[k] for k in ("job", "machine", "exit_code", "source_sha256", "date")}, ensure_ascii=False)); return code


if __name__ == "__main__":
    sys.exit(main())
