# -*- coding: utf-8 -*-
"""Daemon'un kullandığı Python'da hangi modüller/araçlar var? Çıktı: studio/reports/env_probe.json"""
import importlib, json, os, shutil, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
res = {"python": sys.version.split()[0], "modules": {}, "ffmpeg_filters": {}}
for m in ("numpy", "PIL", "edge_tts", "scipy", "soundfile", "cv2", "piper", "pydub"):
    try:
        mod = importlib.import_module(m); res["modules"][m] = getattr(mod, "__version__", "var")
    except Exception as e:  # noqa: BLE001
        res["modules"][m] = "YOK"
ff = shutil.which("ffmpeg")
res["ffmpeg"] = ff
if ff:
    out = subprocess.run([ff, "-hide_banner", "-filters"], capture_output=True, text=True).stdout
    for f in ("acompressor", "highpass", "lowpass", "equalizer", "aecho", "asetrate", "atempo", "dynaudnorm", "alimiter", "areverse", "silenceremove", "xfade", "gblur", "minterpolate", "tblend"):
        res["ffmpeg_filters"][f] = (" " + f + " ") in out
os.makedirs(os.path.join(ROOT, "studio", "reports"), exist_ok=True)
json.dump(res, open(os.path.join(ROOT, "studio", "reports", "env_probe.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False))
