# -*- coding: utf-8 -*-
"""TTS satırı cilası (numpy): baştaki/sondaki sessizliği kırpar (ölü boşluk ve kayık senkron kaynağı), kenarlara kısa fade, seviye eşitleme.
Her satır aynı konuşma seviyesine (RMS) getirilir; tepe %92'yi aşmaz. 16-bit mono WAV üzerinde yerinde çalışır."""
import wave
import numpy as np


def polish_wav(path, lead=0.06, tail=0.18, target_rms=0.11, thr_db=-38.0):
    with wave.open(path, "rb") as w:
        sr, ch, n = w.getframerate(), w.getnchannels(), w.getnframes()
        raw = w.readframes(n)
    x = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    if len(x) < sr * 0.05:
        return {"trimmed": False}
    hop = max(1, int(sr * 0.01))
    nfr = len(x) // hop
    fr = np.sqrt(np.mean(x[:nfr * hop].reshape(nfr, hop) ** 2, axis=1)) + 1e-9
    peak_fr = fr.max()
    act = np.where(fr > peak_fr * (10 ** (thr_db / 20.0)))[0]
    if len(act) == 0:
        return {"trimmed": False}
    a = max(0, int(act[0] * hop - lead * sr)); b = min(len(x), int((act[-1] + 1) * hop + tail * sr))
    y = x[a:b].copy()
    rms = float(np.sqrt(np.mean(y ** 2))) + 1e-9
    g = min(target_rms / rms, 0.92 / (np.max(np.abs(y)) + 1e-9), 4.0)
    y *= g
    f = min(len(y) // 4, int(0.008 * sr))
    if f > 0:
        y[:f] *= np.linspace(0, 1, f); y[-f:] *= np.linspace(1, 0, f)
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((np.clip(y, -1, 1) * 32767).astype("<i2").tobytes())
    return {"trimmed": True, "removed_lead_s": round(a / sr, 3), "removed_tail_s": round((len(x) - b) / sr, 3), "gain": round(float(g), 2)}
