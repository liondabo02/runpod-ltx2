"""AHOS ses kimliği motoru (V12 iskelet): sahibin TEK kaynak sesinden her karakterin sesini yaş/cinsiyete göre türetir.

Bu modül iki şey yapar, ikisi de diziden bağımsızdır (motor kodunda karakter/dizi adı yok):
  1) derive(): karakter kartı (yaş, cinsiyet, isteğe bağlı tarif) + kaynak sesin ortanca perdesi -> SABİT ses ayarları
     (perde kaydırma yarım ton, ses yolu/formant oranı, konuşma hızı, nefeslilik, titreme). Saf fonksiyon: aynı girdi = aynı ayar,
     böylece karakter her bölümde aynı sesi alır. Ayarlar series/<id>/voice_identities.json'a yazılır.
  2) transform_preview(): yalnız standart numpy/scipy ile KABA ÖNİZLEME dönüştürücüsü (yeniden örnekleme + süre koruyan WSOLA).
     Perde ve formant AYNI oranda kayar (bağımsız formant yok); 'doğal ses' iddiası yoktur. Asıl dönüştürme klonlayan bir motorla
     (aday: Chatterbox Multilingual, MIT, Türkçe var) ayrı süreçte yapılacak; o gelene kadar bu yuva sesi duyulabilir kılar.

Cinsiyet kartta yoksa TAHMİN EDİLMEZ (isimden ya da görünüşten): yetişkin/ergen karakter için CINSIYET_EKSIK sorunu döner.
Hedef perde ve ses yolu değerleri yaklaşık yayımlanmış ortalamalardır (yetişkin erkek ~120 Hz, kadın ~210 Hz, küçük çocuk ~280-300 Hz;
ses yolu yetişkin erkek ~17 cm); kesin fizyoloji değil, karakter tasarımı için başlangıç noktasıdır ve sahibin kulağıyla ayarlanır.
"""
import json
import math
import os

import numpy as np

GENDERS = ("female", "male")
_GENDER_ALIASES = {"female": "female", "f": "female", "male": "male", "m": "male"}   # kart değeri dil bağımsız: female/male
# tarif sözleri dizinin kendi verisinden gelir; burada yalnız motorun anladığı ayar adları var
STYLE_KEYS = {"pitch_st": (-4.0, 4.0), "rate": (0.8, 1.25), "breathiness": (0.0, 0.6), "tremolo": (0.0, 0.5)}
MIN_PAIR_DISTANCE = 1.5   # (yarım ton, formant log-oranı*12) uzayında aynı sahnedeki iki karakterin en az uzaklığı


def _gender(card):
    g = card.get("gender") or card.get("sex") or (card.get("voice") or {}).get("gender")
    return _GENDER_ALIASES.get(str(g).strip().lower()) if g else None


def target_f0(age, gender):
    """Yaşa/cinsiyete göre hedef ortanca perde (Hz). Ergenlikten önce cinsiyet farkı küçük tutulur."""
    a = float(age)
    if a < 2:
        return 360.0
    if a < 10:
        return 300.0 - (a - 2) * 5.0                    # 2 yaş ~300 Hz -> 9 yaş ~265 Hz
    if a < 16:                                          # ergenlik: kızlarda ~230'a, erkeklerde ~130'a iner
        k = (a - 10) / 6.0
        end = 230.0 if gender == "female" else 130.0 if gender == "male" else 200.0
        return 260.0 + (end - 260.0) * k
    base = 210.0 if gender == "female" else 120.0 if gender == "male" else 165.0
    if a >= 60:                                         # yaşlılıkta kadın perdesi iner, erkek perdesi biraz çıkar
        base += (-15.0 if gender == "female" else 10.0 if gender == "male" else 0.0) * min(1.0, (a - 60) / 20.0)
    return base


def vocal_tract_cm(age, gender):
    a = float(age)
    adult = 14.5 if gender == "female" else 17.0 if gender == "male" else 15.7
    if a >= 18:
        return adult
    newborn = 8.0
    return newborn + (adult - newborn) * min(1.0, max(0.0, a) / 18.0) ** 0.75


def derive(card, source_f0, source_tract_cm=17.0):
    """-> {"params": {...}, "problems": [str]}. source_f0: kaynak sesin ölçülen ortanca perdesi (Hz)."""
    problems = []
    age = card.get("age")
    if age is None:
        return {"params": None, "problems": ["YAS_EKSIK: karakter kartında yaş yok"]}
    gender = _gender(card)
    if gender is None and float(age) >= 10:
        problems.append("CINSIYET_EKSIK: %s yaşındaki karakter için cinsiyet kartta yok (tahmin edilmez)" % age)
    f0 = target_f0(age, gender)
    st = 12.0 * math.log2(f0 / float(source_f0))
    formant = source_tract_cm / vocal_tract_cm(age, gender)
    style = (card.get("voice") or {}).get("style") or {}
    p = {"pitch_st": round(st, 2), "formant_ratio": round(formant, 3), "rate": 1.0, "breathiness": 0.0,
         "tremolo": 0.15 if float(age) >= 70 else 0.0, "target_f0_hz": round(f0, 1), "gender": gender, "age": age}
    for k, (lo, hi) in STYLE_KEYS.items():
        if k in style:
            try:
                v = float(style[k])
            except (TypeError, ValueError):
                problems.append("STIL_GECERSIZ: %s=%r" % (k, style[k])); continue
            if not lo <= v <= hi:
                problems.append("STIL_SINIR_DISI: %s=%s (%s..%s)" % (k, v, lo, hi)); continue
            p[k] = round(p[k] + v, 2) if k == "pitch_st" else v
    return {"params": p, "problems": problems}


def distance(a, b):
    return math.hypot(a["pitch_st"] - b["pitch_st"], 12.0 * math.log2(a["formant_ratio"] / b["formant_ratio"]))


def identities(characters, source_f0, scenes=None):
    """Tüm karakterler için ayarlar + ayırt edilebilirlik. scenes: [[karakter id, ...], ...]; yoksa herkes birlikte sayılır."""
    out, problems = {}, []
    for c in characters:
        r = derive(c, source_f0)
        out[c["id"]] = r["params"]
        problems += ["%s: %s" % (c["id"], m) for m in r["problems"]]
    groups = scenes or [list(out)]
    seen = set()
    for g in groups:
        ids = [i for i in g if out.get(i)]
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                key = tuple(sorted((ids[i], ids[j])))
                if key in seen:
                    continue
                seen.add(key)
                d = distance(out[ids[i]], out[ids[j]])
                if d < MIN_PAIR_DISTANCE:
                    problems.append("SESLER_AYIRT_EDILEMIYOR: %s ve %s aynı sahnede, uzaklık %.2f < %.1f (stil ile ayırın)" % (key[0], key[1], d, MIN_PAIR_DISTANCE))
    return {"identities": out, "problems": problems}


def write(series_dir, result, source_info):
    path = os.path.join(series_dir, "voice_identities.json")
    json.dump({"source": source_info, "identities": result["identities"], "problems": result["problems"],
               "engine": "voice_identity/preview", "note": "kaba önizleme: perde ve formant aynı oranda kayar; kalite kararı sahipte (A3)"},
              open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return path


# ---------- ölçü ve kaba önizleme dönüştürücü ----------

def median_f0(x, sr, fmin=60.0, fmax=500.0, frame_s=0.04):
    """Otokorelasyonla ortanca perde (Hz); sessiz çerçeveler atlanır. Kaba ama bağımlılıksız."""
    x = np.asarray(x, dtype=np.float64)
    n = int(frame_s * sr); hop = n // 2
    lo, hi = int(sr / fmax), int(sr / fmin)
    vals = []
    for s in range(0, len(x) - n, hop):
        f = x[s:s + n] - x[s:s + n].mean()
        if np.sqrt(np.mean(f * f)) < 1e-3:
            continue
        ac = np.correlate(f, f, "full")[n - 1:]
        if ac[0] <= 0 or hi >= len(ac):
            continue
        lag = lo + int(np.argmax(ac[lo:hi]))
        if ac[lag] / ac[0] > 0.3:
            vals.append(sr / lag)
    return float(np.median(vals)) if vals else None


def _wsola(x, rate, sr, win_s=0.03):
    """Süreyi 1/rate ile değiştirir (perdeyi korur). Basit WSOLA."""
    n = int(win_s * sr); hop_out = n // 2; hop_in = hop_out * rate; tol = n // 4
    w = np.hanning(n)
    out_len = int(len(x) / rate) + n
    y = np.zeros(out_len); norm = np.zeros(out_len)
    pos_in, pos_out, prev = 0.0, 0, None
    while int(pos_in) + n + tol < len(x) and pos_out + n < out_len:
        c = int(pos_in)
        if prev is not None:
            best, bscore = c, -np.inf
            for d in range(-tol, tol + 1, 4):
                s = c + d
                if s < 0 or s + n > len(x):
                    continue
                sc = float(np.dot(x[s:s + n], prev))
                if sc > bscore:
                    best, bscore = s, sc
            c = best
        seg = x[c:c + n]
        y[pos_out:pos_out + n] += seg * w; norm[pos_out:pos_out + n] += w
        nxt = c + hop_out
        prev = x[nxt:nxt + n] if nxt + n <= len(x) else None
        pos_in += hop_in; pos_out += hop_out
    norm[norm < 1e-6] = 1.0
    return y / norm


def transform_preview(x, sr, params):
    """Kaynak sesi karakter ayarına KABA olarak çevirir: perde = formant oranı = 2^(st/12); süre korunur (hız ayarı hariç).
    Dönüş: aynı sr'de float dizi. Bağımsız formant kaydırma YOK (asıl motor gelene kadar)."""
    from scipy.signal import resample_poly
    from fractions import Fraction
    x = np.asarray(x, dtype=np.float64)
    ratio = 2.0 ** (float(params["pitch_st"]) / 12.0)
    fr = Fraction(ratio).limit_denominator(200)
    y = resample_poly(x, fr.denominator, fr.numerator)          # kısalır, perde ratio kadar yükselir
    y = _wsola(y, 1.0 / ratio * float(params.get("rate", 1.0)), sr)  # süreyi geri uzat (hız ayarıyla)
    target = int(len(x) / float(params.get("rate", 1.0)))
    y = y[:target] if len(y) >= target else np.pad(y, (0, target - len(y)))
    b = float(params.get("breathiness", 0.0))
    if b > 0:
        rng = np.random.default_rng(0)
        env = np.abs(y); env = np.convolve(env, np.ones(int(0.01 * sr)) / int(0.01 * sr), "same")
        y = y + b * 0.3 * env * rng.standard_normal(len(y))
    t = float(params.get("tremolo", 0.0))
    if t > 0:
        y = y * (1.0 + t * 0.3 * np.sin(2 * np.pi * 5.5 * np.arange(len(y)) / sr))
    peak = np.max(np.abs(y)) or 1.0
    return y * min(1.0, 0.95 / peak)
