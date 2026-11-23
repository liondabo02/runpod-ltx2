# -*- coding: utf-8 -*-
"""AHOS skor motoru (numpy, yerel, telifsiz). Rastgele tıngırtı değil, besteli müzik üretir:
- Dizi kimliğinden (series_id) sabit anahtar, tempo, akor ilerlemesi ve 8 ölçülük ANA TEMA (her bölümde aynı tema geri gelir).
- Katmanlar: bas, ukulele tıngırtısı (ritmik), marimba/müzik kutusu melodisi, pad, shaker/kick/el çırpma, glockenspiel parıltı.
- Katman yoğunluğu sahnenin duygusuna (arousal/valence) göre yumuşakça açılıp kapanır; sahne geçişlerinde kısa 'ting' + süpürme.
- Diyalog sırasında müzik yumuşakça kısılır (sidechain), ortak yankı (reverb) ile tek mekânda çalıyormuş gibi birleşir.
Çıktı mono float32 [-1,1] SR=22050. Müziğin 'güzelliği' kulakla sahip tarafından onaylanır; burada yalnız teknik özellikler ölçülür."""
import hashlib, math, random
import numpy as np

SR = 22050
BPM = 100.0
BEAT = 60.0 / BPM
BAR = 4 * BEAT
MAJ = [0, 2, 4, 5, 7, 9, 11]
MIN = [0, 2, 3, 5, 7, 8, 10]


def _seed(series_id):
    return int(hashlib.sha1(str(series_id).encode()).hexdigest()[:8], 16)


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12.0)


def theme(series_id):
    r = random.Random(_seed(series_id))
    root = r.choice([55, 57, 60, 62])                       # G3, A3, C4, D4
    prog = r.choice([[0, 4, 5, 3], [0, 5, 3, 4], [0, 3, 4, 0], [0, 4, 3, 4]])   # I V vi IV tarzı (derece indeksleri majör diziden)
    # 8 ölçülük melodi: ölçü başına 4 vuruş, her vuruşta en çok 2 nota. (vuruş_konumu, derece, süre_vuruş)
    mel = []
    deg = r.choice([2, 4, 2])
    rhythms = [[(0, 1.0), (1, 0.5), (1.5, 0.5), (2, 1.0), (3, 1.0)], [(0, 0.5), (0.5, 0.5), (1, 1.0), (2, 2.0)],
               [(0, 1.5), (1.5, 0.5), (2, 1.0), (3, 1.0)], [(0, 1.0), (1, 1.0), (2, 0.5), (2.5, 0.5), (3, 1.0)]]
    chord_deg = lambda bar: prog[(bar // 2) % 4]
    for bar in range(8):
        cd = chord_deg(bar)
        tones = [cd % 7, (cd + 2) % 7, (cd + 4) % 7]
        pat = rhythms[(bar + r.randrange(2)) % 4] if bar not in (3, 7) else rhythms[1]
        for i, (pos, dur) in enumerate(pat):
            if pos in (0, 2) or i == 0:                        # güçlü vuruşta akor sesi
                tgt = min(tones, key=lambda d: abs(d - deg % 7))
                deg = tgt + 7 * (deg // 7)
            else:                                              # diğerleri adım adım
                deg += r.choice([-1, 1, 1, -1, 0]) if bar not in (7,) else -1
            deg = max(0, min(11, deg))
            mel.append((bar * 4 + pos, deg, dur))
        if bar == 7 and mel:                                   # tema akor sesine oturarak biter
            p, _, d = mel[-1]; mel[-1] = (p, 0 if r.random() < 0.5 else 4, max(d, 2.0))
    return {"root": root, "prog": prog, "melody": mel, "bpm": BPM}


def _add(buf, t0, x, gain=1.0):
    i0 = int(t0 * SR)
    if i0 >= len(buf) or i0 + len(x) <= 0:
        return
    a = max(0, -i0); b = min(len(x), len(buf) - i0)
    buf[i0 + a:i0 + b] += x[a:b] * gain


def _t(dur):
    return np.arange(int(dur * SR)) / SR


def _env(t, attack=0.004, decay=4.0):
    return np.minimum(1.0, t / attack) * np.exp(-t * decay)


def pluck(f, dur=0.6, bright=1.0):
    t = _t(dur); y = np.zeros_like(t)
    for h in range(1, 7):
        y += (1.0 / h ** 1.25) * np.sin(2 * np.pi * f * h * t) * np.exp(-t * (2.5 + 2.2 * h / max(0.4, bright)))
    return y * np.minimum(1.0, t / 0.003)


def marimba(f, dur=0.5):
    t = _t(dur)
    y = np.sin(2 * np.pi * f * t) * np.exp(-t * 7.5) + 0.35 * np.sin(2 * np.pi * f * 3.97 * t) * np.exp(-t * 22) + 0.12 * np.sin(2 * np.pi * f * 9.2 * t) * np.exp(-t * 40)
    return y * np.minimum(1.0, t / 0.002)


def musicbox(f, dur=0.9):
    t = _t(dur)
    y = np.sin(2 * np.pi * f * t) * np.exp(-t * 3.2) + 0.45 * np.sin(2 * np.pi * f * 2.0 * t) * np.exp(-t * 5) + 0.2 * np.sin(2 * np.pi * f * 4.0 * t) * np.exp(-t * 9)
    return y * np.minimum(1.0, t / 0.002)


def glock(f, dur=0.8):
    t = _t(dur)
    return (np.sin(2 * np.pi * f * t) + 0.5 * np.sin(2 * np.pi * f * 2.76 * t) * np.exp(-t * 3)) * np.exp(-t * 4.0) * np.minimum(1.0, t / 0.001)


def bass(f, dur=0.45):
    t = _t(dur)
    return (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * 2 * f * t)) * np.minimum(1.0, t / 0.006) * np.exp(-t * 3.6)


def pad_note(f, dur):
    t = _t(dur)
    env = np.minimum(1.0, t / 0.6) * np.minimum(1.0, np.maximum(0.0, (dur - t) / 0.7))
    return (np.sin(2 * np.pi * f * t) + 0.6 * np.sin(2 * np.pi * f * 1.004 * t) + 0.25 * np.sin(2 * np.pi * f * 2 * t)) * env


def kick():
    t = _t(0.18); f = 45 + 90 * np.exp(-t * 28)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 17)


def shaker(rng, dur=0.07):
    t = _t(dur); n = rng.standard_normal(len(t)); n = np.diff(n, prepend=0)
    return n * np.exp(-t * 55) * 0.6


def clap(rng):
    t = _t(0.12); n = rng.standard_normal(len(t)); n = np.diff(n, prepend=0)
    return n * (np.exp(-t * 45) + 0.6 * np.exp(-np.maximum(0, t - 0.015) * 60) * (t > 0.015))


def whoosh(rng, dur=0.5):
    t = _t(dur); n = rng.standard_normal(len(t))
    k = 40; n = np.convolve(n, np.ones(k) / k, mode="same")
    return n * np.sin(np.pi * t / dur) ** 2 * 1.8


def _reverb(x, rng, secs=1.1, wet=0.2):
    n = int(secs * SR); t = np.arange(n) / SR
    ir = rng.standard_normal(n) * np.exp(-t * 4.2); ir[0] = 0
    ir /= np.sqrt(np.sum(ir ** 2)) + 1e-9
    L = 1
    while L < len(x) + n:
        L *= 2
    y = np.fft.irfft(np.fft.rfft(x, L) * np.fft.rfft(ir, L), L)[:len(x)]
    return x * (1 - wet) + y * wet * 3.0


def _intensity(sheet, total):
    """Saniye başına arousal/valence eğrisi (yumuşatılmış) + sahne sınırları."""
    n = int(total) + 2
    ar = np.full(n, 0.45); va = np.full(n, 0.55); bounds = []
    prev = None
    for b in sheet["beats"]:
        e = b.get("emotion") or {}
        try:
            a = float(e.get("arousal", 0.45)); v = float(e.get("valence", 0.55))
        except (TypeError, ValueError):
            a, v = 0.45, 0.55
        s, en = int(float(b["t_start"])), int(math.ceil(float(b["t_end"])))
        ar[s:en] = a; va[s:en] = v
        sc = b.get("scene_id")
        if prev is not None and sc != prev:
            bounds.append(float(b["t_start"]))
        prev = sc
    k = 5
    sm = lambda x: np.convolve(np.pad(x, (k, k), mode="edge"), np.ones(2 * k + 1) / (2 * k + 1), mode="valid")
    return sm(ar), sm(va), bounds


def _duck(total, speech, floor=0.42):
    n = int(total * SR) + SR
    env = np.ones(n, dtype=np.float32)
    for s, e in speech:
        env[int(max(0, s) * SR):int(min(total, e) * SR) + 1] = floor
    k = int(0.22 * SR)
    c = np.cumsum(np.pad(env, (k, k), mode="edge"), dtype=np.float64)
    return ((c[2 * k:] - c[:-2 * k]) / (2 * k))[:n].astype(np.float32) if len(c) - 2 * k >= n else env


def compose(sheet, series_id, speech=(), music_gain=1.0):
    total = float(sheet["beats"][-1]["t_end"])
    n = int(total * SR) + SR
    th = theme(series_id); rng = np.random.default_rng(_seed(series_id) % (2 ** 32))
    ar, va, bounds = _intensity(sheet, total)
    lvl = lambda t, thr, w=0.25: float(np.clip((ar[min(int(t), len(ar) - 1)] - thr) / w, 0.0, 1.0))
    root = th["root"]
    bus_tonal = np.zeros(n, dtype=np.float32)       # yankı alacak
    bus_dry = np.zeros(n, dtype=np.float32)
    nbars = int(total / BAR) + 2
    for bar in range(nbars):
        t0 = bar * BAR
        if t0 >= total: break
        tm = min(total - 0.01, t0 + BAR / 2)
        a = float(ar[min(int(tm), len(ar) - 1)]); v = float(va[min(int(tm), len(va) - 1)])
        minor = v < 0.38
        scale = MIN if minor else MAJ
        cd = th["prog"][(bar // 2) % 4]
        cr = root + scale[cd % 7] + (12 if cd >= 7 else 0)
        third = root + scale[(cd + 2) % 7] + (12 if cd + 2 >= 7 else 0)
        fifth = root + scale[(cd + 4) % 7] + (12 if cd + 4 >= 7 else 0)
        chord = [cr, third, fifth]
        # pad (her zaman çok hafif)
        for m in chord:
            _add(bus_tonal, t0, pad_note(hz(m), BAR + 0.4), 0.05 + 0.04 * (1 - a))
        # bas: kök-beşli
        if a > 0.25:
            for i, (off, m) in enumerate(((0, cr - 24), (1.5, cr - 24), (2, fifth - 24), (3.5, cr - 12))):
                _add(bus_dry, t0 + off * BEAT, bass(hz(m)), 0.38 * lvl(tm, 0.25, 0.2))
        # ukulele: ritmik tıngırtı (aşağı-yukarı) veya sakin arpej
        if a >= 0.42:
            for off, g in ((0, 1.0), (1, 0.6), (1.5, 0.8), (2.5, 0.8), (3, 0.6)):
                for j, m in enumerate(chord + [cr + 12]):
                    _add(bus_tonal, t0 + off * BEAT + j * 0.012, pluck(hz(m + 12), 0.5), 0.085 * g * lvl(tm, 0.42, 0.15))
        else:
            for k, m in enumerate((chord[0], chord[1], chord[2], chord[1], chord[2], chord[1], chord[0], chord[1])):
                _add(bus_tonal, t0 + k * BEAT / 2, pluck(hz(m + 12), 0.7, 0.7), 0.075)
        # ritim
        if a > 0.5:
            for k in range(8):
                _add(bus_dry, t0 + k * BEAT / 2, shaker(rng), 0.10 * lvl(tm, 0.5, 0.15) * (1.0 if k % 2 == 0 else 0.6))
            for off in (0, 2):
                _add(bus_dry, t0 + off * BEAT, kick(), 0.30 * lvl(tm, 0.55, 0.15))
            for off in (1, 3):
                _add(bus_dry, t0 + off * BEAT, clap(rng), 0.16 * lvl(tm, 0.6, 0.15))
    # ana tema: 8 ölçü döngü; sahne yoğunluğuna göre enstrüman
    for rep in range(int(total / (8 * BAR)) + 1):
        base = rep * 8 * BAR
        for (pos, degree, dur) in th["melody"]:
            t = base + pos * BEAT
            if t >= total: continue
            a = float(ar[min(int(t), len(ar) - 1)]); v = float(va[min(int(t), len(va) - 1)])
            scale = MIN if v < 0.38 else MAJ
            m = root + 12 + scale[degree % 7] + 12 * (degree // 7)
            d = min(1.2, dur * BEAT + 0.3)
            if a < 0.38:
                _add(bus_tonal, t, musicbox(hz(m), d + 0.4), 0.16)
            else:
                _add(bus_tonal, t, marimba(hz(m), d), 0.24)
                if a > 0.6:
                    _add(bus_tonal, t, marimba(hz(m + 12), d), 0.08)
    # sahne geçişi: parıltı + süpürme
    for tb in bounds:
        _add(bus_tonal, tb - 0.05, glock(hz(root + 24 + MAJ[4])), 0.2)
        _add(bus_tonal, tb + 0.1, glock(hz(root + 36)), 0.12)
        _add(bus_dry, tb - 0.35, whoosh(rng), 0.10)
    # açılış: ilk 3 sn glock motifi
    for i, st in enumerate((0, 4, 7, 12)):
        _add(bus_tonal, 0.2 + i * 0.35, glock(hz(root + 24 + st)), 0.22)
    # kapanış: son ölçüde akor + sönüm
    for m in (root, root + 4, root + 7, root + 12):
        _add(bus_tonal, max(0.0, total - 2.4), pluck(hz(m + 12), 2.4, 0.6), 0.12)
    wet = _reverb(bus_tonal, rng)
    mix = wet + bus_dry
    mix *= _duck(total, speech)[:n]
    # kenar yumuşatma
    fade = int(1.5 * SR); mix[-fade:] *= np.linspace(1, 0, fade)
    peak = np.max(np.abs(mix)) + 1e-9
    mix = np.tanh(mix / peak * 1.4) * 0.72 * music_gain
    return mix.astype(np.float32)


def stats(x):
    r = float(np.sqrt(np.mean(x.astype(np.float64) ** 2)))
    return {"peak": float(np.max(np.abs(x))), "rms": r, "seconds": round(len(x) / SR, 1)}
