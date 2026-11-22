#!/usr/bin/env python3
"""AHOS motor sağlık kontrolü (salt okunur, yalnız standart kütüphane).

Kullanım: python tools/engine_check.py
Her motor için OK / EKSIK yazar; hiçbir şey kurmaz, indirmez, harcama yapmaz.
"""
import importlib.util, json, os, shutil, subprocess, sys, urllib.error, urllib.request

BLENDER_DIRS = [r"C:\actions-runner\_work\blender-4.5.16-windows-x64"]
RHUBARB_DIRS = [r"C:\actions-runner\_work\tools\rhubarb", r"C:\actions-runner\_work\tools\rhubarb\Rhubarb-Lip-Sync-1.14.0-Windows"]
HERE = os.path.dirname(os.path.abspath(__file__))  # repo tools/ (blender.cmd, rhubarb.cmd)
BLENDER_DIRS.append(HERE); RHUBARB_DIRS.append(HERE)


def run(cmd):
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return (out.stdout or out.stderr).strip().splitlines()[0] if (out.stdout or out.stderr) else "?"
    except Exception as e:
        return None


def http(url, timeout=5):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, r.read()[:2000]
    except urllib.error.HTTPError as e:   # 401/404 vb. = sunucu AÇIK, sadece o yola izin yok
        return e.code, b""
    except Exception as e:
        return None, str(e)


def find(name, dirs):
    p = shutil.which(name)
    if p: return p
    for d in dirs:
        for ext in ("", ".exe", ".cmd"):
            c = os.path.join(d, name + ext)
            if os.path.exists(c): return c
    return None


def main():
    rows = []
    rows.append(("Python", "OK", sys.version.split()[0]))
    for n in ("ffmpeg", "ffprobe"):
        p = find(n, [])
        rows.append((n, "OK" if p else "EKSIK", (run([p, "-version"]) if p else "PATH'te yok")))
    b = find("blender", BLENDER_DIRS)
    rows.append(("Blender", "OK" if b else "EKSIK", (run([b, "--version"]) if b else "bulunamadı")))
    r = find("rhubarb", RHUBARB_DIRS)
    rows.append(("Rhubarb (dudak senkronu)", "OK" if r else "EKSIK", (run([r, "--version"]) if r else "bulunamadı")))
    rows.append(("edge-tts (ses)", "OK" if importlib.util.find_spec("edge_tts") else "EKSIK",
                 "python modülü" if importlib.util.find_spec("edge_tts") else "pip install edge-tts"))
    st, body = http(os.environ.get("AHOS_LLM_BASE", "http://localhost:20128/v1").rstrip("/") + "/models")
    n = ""
    if st == 200:
        try: n = f"{len(json.loads(body.decode() if isinstance(body, bytes) else body).get('data', []))}+ model"
        except Exception: n = "yanıt var"
    rows.append(("OmniRoute (LLM ağ geçidi)", "OK" if st else "KAPALI", (n or ("açık (HTTP %s)" % st)) if st else "http://localhost:20128 açık değil -> 'omniroute' çalıştır"))
    st, _ = http("http://localhost:3001/")
    rows.append(("FreeLLMAPI", "OK" if st else "KAPALI", "http://localhost:3001" if st else "kapalı -> npm run dev"))
    du = shutil.disk_usage(os.path.abspath(os.sep))
    free = du.free / 1e9
    rows.append(("Boş disk", "OK" if free >= 20 else "DÜŞÜK", f"{free:.1f} GB (en az 20 GB önerilir)"))
    w = max(len(x[0]) for x in rows)
    for name, st, info in rows:
        print(f"{name.ljust(w)}  {st.ljust(6)}  {info}")
    bad = [x for x in rows if x[1] != "OK"]
    print("\nSONUÇ:", "tüm motorlar hazır" if not bad else f"{len(bad)} sorun: " + ", ".join(x[0] for x in bad))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
