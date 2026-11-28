#!/usr/bin/env python3
"""AHOS ses kimliği arka ucu (V12 c): AYRI SÜREÇTE çalışır (ayrı Python ortamı: AHOS_VOICE_PY), AHOS'un kendi paketlerine dokunmaz.

Zincir: metin -> Chatterbox Multilingual (kaynak sesin tınısında, MIT) -> WORLD (pyworld, MIT; WORLD modified-BSD) ile
perde ve ses yolu (formant) AYRI kaydırılır -> karakter sesi.

Kullanım (iş listesi JSON):
  <venv_python> tools/voice_backend.py --jobs jobs.json --ref kaynak.wav --report rapor.json
  jobs.json = [{"text": "...", "lang": "tr", "params": {voice_identity ayarı}, "out": "x.wav"}, ...]
Kaynak ses dosyası depoya girmez. Model dosyaları HF_HOME altında (models/hf, .gitignore).
Kalite ('doğal mı') ölçülmez, sahibin kulağına kalır; burada yalnız teknik ölçü (süre, perde, üretim süresi) yazılır.
"""
import argparse
import json
import os
import sys
import time

import numpy as np


def world_transform(x, sr, params):
    """Perde: f0 * 2^(pitch_st/12). Ses yolu: tayf zarfı frekans ekseninde formant_ratio ile ölçeklenir (kısa ses yolu = yukarı).
    Nefeslilik: periyodik olmayan bileşen artırılır. Titreme: f0'a 5.5 Hz salınım."""
    import pyworld as pw
    x = np.asarray(x, dtype=np.float64)
    f0, t = pw.harvest(x, sr)
    sp = pw.cheaptrick(x, f0, t, sr)
    ap = pw.d4c(x, f0, t, sr)
    ratio = 2.0 ** (float(params.get("pitch_st", 0.0)) / 12.0)
    f0n = f0 * ratio
    trem = float(params.get("tremolo", 0.0))
    if trem > 0:
        f0n = f0n * (1.0 + trem * 0.04 * np.sin(2 * np.pi * 5.5 * t))
    fr = float(params.get("formant_ratio", 1.0))
    if abs(fr - 1.0) > 1e-3:
        bins = sp.shape[1]
        src = np.arange(bins) / fr                 # yeni k. kutu eski k/fr. kutudan gelir
        sp = np.stack([np.interp(src, np.arange(bins), row, right=row[-1]) for row in sp])
        ap = np.stack([np.interp(src, np.arange(bins), row, right=row[-1]) for row in ap])
    b = float(params.get("breathiness", 0.0))
    if b > 0:
        ap = np.clip(ap + b * 0.5 * (1.0 - ap), 0.0, 1.0)
    y = pw.synthesize(f0n, sp, ap, sr)
    rate = float(params.get("rate", 1.0))
    if abs(rate - 1.0) > 1e-3:                     # hız: zaman ekseninde yeniden örnekle (perde WORLD'de korunur)
        n = int(len(t) / rate)
        idx = np.linspace(0, len(t) - 1, n)
        f0r = np.interp(idx, np.arange(len(t)), f0n)
        spr = np.stack([np.interp(idx, np.arange(len(t)), sp[:, k]) for k in range(sp.shape[1])], axis=1)
        apr = np.stack([np.interp(idx, np.arange(len(t)), ap[:, k]) for k in range(ap.shape[1])], axis=1)
        y = pw.synthesize(np.ascontiguousarray(f0r), np.ascontiguousarray(spr), np.ascontiguousarray(apr), sr)
    peak = float(np.max(np.abs(y))) or 1.0
    return (y * min(1.0, 0.95 / peak)).astype(np.float32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", required=True); ap.add_argument("--ref", required=True); ap.add_argument("--report", required=True)
    ap.add_argument("--device", default="cpu")
    a = ap.parse_args()
    jobs = json.load(open(a.jobs, encoding="utf-8"))
    rep = {"engine": "chatterbox-multilingual+world", "licence": {"chatterbox": "MIT (kod ve model kartı)", "pyworld": "MIT", "WORLD": "modified-BSD"},
           "watermark": "Chatterbox çıktısına Perth damgası eklenir", "items": []}
    if not os.path.exists(a.ref):
        rep["status"] = "KAYNAK_SES_YOK"; json.dump(rep, open(a.report, "w", encoding="utf-8"), ensure_ascii=False, indent=2); sys.exit(2)
    import torch  # noqa: F401
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS
    t0 = time.time(); model = ChatterboxMultilingualTTS.from_pretrained(device=a.device); rep["load_s"] = round(time.time() - t0, 1)
    sr = model.sr
    for j in jobs:
        it = {"out": j["out"], "lang": j["lang"]}
        try:
            t0 = time.time()
            wav = model.generate(j["text"], language_id=j["lang"], audio_prompt_path=a.ref).squeeze().cpu().numpy()
            it["clone_s"] = round(time.time() - t0, 1)
            t0 = time.time(); y = world_transform(wav, sr, j.get("params") or {}); it["world_s"] = round(time.time() - t0, 1)
            import soundfile as sf
            os.makedirs(os.path.dirname(os.path.abspath(j["out"])), exist_ok=True)
            sf.write(j["out"], y, sr)
            it["audio_s"] = round(len(y) / sr, 2); it["status"] = "OK"
        except Exception as e:  # noqa: BLE001
            it["status"] = "HATA"; it["error"] = repr(e)[:300]
        rep["items"].append(it)
    rep["status"] = "OK" if all(i["status"] == "OK" for i in rep["items"]) else "KISMI"
    json.dump(rep, open(a.report, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    sys.exit(0 if rep["status"] == "OK" else 3)


if __name__ == "__main__":
    main()
