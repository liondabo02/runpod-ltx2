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


def main():
    a = sys.argv[1:]; i = a.index("--"); label, job, out = a[0], a[1], a[2]; cmd = a[i + 1:]
    sh = dev_cmd.src_hash(ROOT)
    c = job_ledger.claim(ROOT, job, label, sh)
    rec = {"job": job, "machine": label, "claim": c, "source_sha256": sh, "command": cmd, "date": datetime.datetime.now().isoformat(timespec="seconds"), "info": machine_info()}
    if not c["ok"] or c["action"] == "DONE":
        json.dump(rec, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1); print(c); return 0 if c["ok"] else 4
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    rec.update(exit_code=r.returncode, raw_tail=(r.stdout or "")[-1500:] + (r.stderr or "")[-500:])
    json.dump(rec, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if r.returncode == 0:
        job_ledger.complete(ROOT, job, label, out)
    else:
        job_ledger.fail(ROOT, job, label, "exit %d" % r.returncode)
    print(json.dumps({k: rec[k] for k in ("job", "machine", "exit_code", "source_sha256", "date")}, ensure_ascii=False)); return r.returncode


if __name__ == "__main__":
    sys.exit(main())
