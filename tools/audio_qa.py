"""Ses teknik denetimi (insan dinlemesinin YERİNE GEÇMEZ): clipping, sessizlik, kesilme, süre-metin uyumu,
konuşma/müzik oranı. Ortalama dB tek başına kalite sonucu değildir; bu kontroller ayrı ayrı raporlanır."""
import wave, math, re
import numpy as np

def read_wav(path):
    with wave.open(path, "rb") as w:
        sr = w.getframerate(); n = w.getnframes(); ch = w.getnchannels(); sw = w.getsampwidth()
        raw = w.readframes(n)
    if sw != 2: raise ValueError("yalnız 16-bit wav")
    x = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    if ch > 1: x = x.reshape(-1, ch).mean(axis=1)
    return x, sr

def db(v): return 20 * math.log10(max(v, 1e-9))

def _win_rms(x, sr, ms=20):
    n = max(1, int(sr * ms / 1000)); m = len(x) // n
    if m == 0: return np.array([float(np.sqrt(np.mean(x ** 2)) if len(x) else 0.0)])
    return np.sqrt(np.mean(x[:m * n].reshape(m, n) ** 2, axis=1))

def stats(x, sr, floor_db=-50.0):
    r = _win_rms(x, sr); act = r > 10 ** (floor_db / 20)
    idx = np.where(act)[0]
    lead = (idx[0] * 0.02) if len(idx) else len(x) / sr
    trail = ((len(r) - 1 - idx[-1]) * 0.02) if len(idx) else len(x) / sr
    return {"dur": len(x) / sr, "peak_db": db(float(np.max(np.abs(x)) if len(x) else 0)),
            "rms_db": db(float(np.sqrt(np.mean(x ** 2)) if len(x) else 0)),
            "clip_frac": float(np.mean(np.abs(x) >= 0.999)) if len(x) else 0.0,
            "speech_ratio": float(np.mean(act)), "lead_s": lead, "trail_s": trail,
            "end_level_db": db(float(np.sqrt(np.mean(x[-max(1, int(sr * 0.005)):] ** 2)) if len(x) else 0))}

def validate_speech(x, sr, text, lang="tr"):
    """Bir replik dosyası için sorun listesi (boş = geçti). Metin eksilmesi/kesilme/sessizlik/clipping."""
    probs = []; s = stats(x, sr)
    letters = len(re.findall(r"\w", text, re.U))
    if s["dur"] <= 0.05 or s["speech_ratio"] < 0.15: probs.append("SESSİZ_VEYA_BOŞ")
    if letters:
        cps = letters / max(s["dur"], 1e-3)                     # saniyede harf
        if cps > 24: probs.append("METİN_EKSİK_OLASI (süre metne göre çok kısa: %.0f harf/sn)" % cps)
        if cps < 4 and s["dur"] > 1.0: probs.append("ÇOK_UZUN_VEYA_BOŞLUKLU (%.1f harf/sn)" % cps)
    if s["clip_frac"] > 0.001: probs.append("CLIPPING (%.3f%% örnek)" % (100 * s["clip_frac"]))
    if s["end_level_db"] > -40: probs.append("KESİLME_OLASI (dosya yüksek seviyede bitiyor)")
    return probs, s

def speech_over_music_db(speech, music, sr, floor_db=-45.0):
    """Konuşma aktifken konuşma/müzik RMS farkı (dB). Küçük fark = müzik konuşmayı bastırıyor. En düşük pencere yüzdelik 10."""
    n = min(len(speech), len(music)); speech, music = speech[:n], music[:n]
    rs, rm = _win_rms(speech, sr, 100), _win_rms(music, sr, 100); k = min(len(rs), len(rm))
    act = rs[:k] > 10 ** (floor_db / 20)
    if not act.any(): return None
    d = [db(a) - db(b) for a, b in zip(rs[:k][act], rm[:k][act])]
    return float(np.percentile(d, 10))

def ducking_db(speech, music, sr, floor_db=-45.0):
    """Müziğin konuşma sırasında, konuşma olmayan anlara göre kaç dB kısıldığı."""
    n = min(len(speech), len(music)); speech, music = speech[:n], music[:n]
    rs, rm = _win_rms(speech, sr, 100), _win_rms(music, sr, 100); k = min(len(rs), len(rm))
    act = rs[:k] > 10 ** (floor_db / 20)
    if not act.any() or act.all(): return None
    return db(float(np.mean(rm[:k][~act]))) - db(float(np.mean(rm[:k][act])))
