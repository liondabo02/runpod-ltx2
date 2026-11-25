#!/usr/bin/env python3
"""Piper Türkçe ses modellerini indirir. DİKKAT: piper kodu MIT, ama SES VERİSİ lisansı sese göre değişir (dfki = CC BY-NC-SA, ticari DEĞİL; bkz. tools/voice_licence.py). Kullanım: python tools/get_piper_voice.py [model_adı]"""
import os, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main/tr/tr_TR/%s/medium/tr_TR-%s-medium.onnx"
VOICES = ["dfki", "fahrettin", "fettah"]


def fetch(url, dest):
    with urllib.request.urlopen(url, timeout=120) as r, open(dest, "wb") as f:
        f.write(r.read())
    return os.path.getsize(dest)


def main():
    out = os.environ.get("AHOS_PIPER_DIR") or os.path.join(ROOT, "models", "piper")
    os.makedirs(out, exist_ok=True)
    names = sys.argv[1:] or VOICES
    for v in names:
        base = BASE % (v, v)
        try:
            a = fetch(base, os.path.join(out, "tr_TR-%s-medium.onnx" % v))
            b = fetch(base + ".json", os.path.join(out, "tr_TR-%s-medium.onnx.json" % v))
            print("İNDİRİLDİ %s (%.1f MB)" % (v, (a + b) / 1e6))
        except Exception as e:
            print("İNDİRİLEMEDİ %s: %s" % (v, e))


if __name__ == "__main__":
    main()
