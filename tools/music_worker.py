#!/usr/bin/env python3
"""AHOS Müzik & Efekt işçisi — diziden bağımsız, tamamen yerel, telifsiz (kodla üretilir, para harcamaz).

- Müzik: dizinin kimliğinden (series_id) sabit bir ana ton/tema seçilir => aynı dizide tutarlı müzik.
  Vuruşun duygusuna (valence/arousal) göre tempo ve ses dizisi (majör/minör pentatonik) değişir.
- Efekt: eylem metnindeki anahtar kelimelerden (koş, zıpla, şaşır, kapı...) basit efektler.
- Diyalog sırasında müzik kısılır (ducking), konuşma her zaman net duyulur.
Çıktı: <bölüm>/audio/bed.wav (22.05 kHz mono) ve mix() ile diyalog zaman çizelgesiyle birleştirme.
"""
import argparse, array, hashlib, json, math, os, random, shutil, struct, subprocess, sys, wave

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
SR = 22050
MAJOR = [0, 2, 4, 7, 9]          # majör pentatonik
MINOR = [0, 3, 5, 7, 10]         # minör pentatonik
SFX_RULES = [
    (("koş", "kosu", "fırla", "kaç"), "run"), (("yürü", "adım"), "step"), (("zıpla", "atla", "hoplar"), "boing"),
    (("şaşır", "irkil", "hay aksi"), "whoop"), (("kapı", "tıkla", "çal"), "knock"), (("büyü", "ışılda", "parla", "yıldız"), "sparkle"),
    (("düş", "çarp", "patla"), "pop"), (("rüzgar", "rüzgâr", "uçur", "fırtına"), "whoosh"),
]


def seed_of(series_id):
    return int(hashlib.sha1(str(series_id).encode()).hexdigest()[:8], 16)


def theme(series_id):
    r = random.Random(seed_of(series_id))
    return {"root": r.choice([57, 59, 60, 62, 64, 65]), "motif": [r.choice(range(5)) for _ in range(4)], "swing": r.choice([0.0, 0.08])}


def hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12.0)


def mood(beat):
    e = beat.get("emotion") or {}
    try:
        v = float(e.get("valence", 0.3)); a = float(e.get("arousal", 0.4))
    except (TypeError, ValueError):
        v, a = 0.3, 0.4
    return v, a


def _add(buf, start_s, samples, gain=1.0):
    i0 = int(start_s * SR)
    n = len(buf)
    for k, x in enumerate(samples):
        j = i0 + k
        if j >= n: break
        buf[j] += x * gain


def pluck(freq, dur=0.45, tri=True):
    n = int(SR * dur); out = []
    for k in range(n):
        t = k / SR; ph = (t * freq) % 1.0
        w = (4 * abs(ph - 0.5) - 1) if tri else math.sin(2 * math.pi * ph)
        out.append(w * math.exp(-t * 7.0) * min(1.0, k / 120.0))
    return out


def pad(freq, dur):
    n = int(SR * dur); out = []
    for k in range(n):
        t = k / SR
        env = min(1.0, t / 0.25) * min(1.0, (dur - t) / 0.3 if dur > 0.3 else 1.0)
        out.append((math.sin(2 * math.pi * freq * t) + 0.5 * math.sin(2 * math.pi * freq * 2.005 * t)) * 0.5 * env)
    return out


def sfx_wave(kind, rnd):
    if kind in ("run", "step"):
        n = int(SR * 0.05); return [(rnd.random() * 2 - 1) * math.exp(-k / (SR * 0.012)) for k in range(n)]
    if kind == "boing":
        n = int(SR * 0.35); ph = 0.0; out = []
        for k in range(n):
            t = k / SR; f = 260 + 380 * math.sin(math.pi * min(1.0, t / 0.35)); ph += 2 * math.pi * f / SR
            out.append(math.sin(ph) * math.exp(-t * 5)); 
        return out
    if kind == "whoop":
        n = int(SR * 0.4); ph = 0.0; out = []
        for k in range(n):
            t = k / SR; f = 300 + 900 * (t / 0.4); ph += 2 * math.pi * f / SR
            out.append(math.sin(ph) * min(1.0, t / 0.03) * math.exp(-t * 3))
        return out
    if kind == "knock":
        n = int(SR * 0.09); return [math.sin(2 * math.pi * 170 * k / SR) * math.exp(-k / (SR * 0.03)) for k in range(n)]
    if kind == "pop":
        n = int(SR * 0.12); return [math.sin(2 * math.pi * (500 - 2500 * (k / SR)) * k / SR) * math.exp(-k / (SR * 0.04)) for k in range(n)]
    if kind == "whoosh":
        n = int(SR * 0.7); out = []; lp = 0.0
        for k in range(n):
            t = k / SR; a = 0.05 + 0.5 * math.sin(math.pi * t / 0.7)
            lp += a * ((rnd.random() * 2 - 1) - lp); out.append(lp * math.sin(math.pi * t / 0.7))
        return out
    if kind == "sparkle":
        out = []
        for j, m in enumerate((84, 88, 91, 96)):
            out += [0.0] * int(SR * 0.05) + [x * 0.6 for x in pluck(hz(m), 0.25, tri=False)]
        return out
    return []


def duck_envelope(total_s, speech, floor=0.3):
    env = array.array("f", [1.0]) * int(total_s * SR + SR)
    ramp = int(0.15 * SR)
    for s, e in speech:
        a, b = int(max(0, s) * SR), int(min(total_s, e) * SR)
        for i in range(max(0, a), min(len(env), b)):
            env[i] = floor
        for k in range(ramp):
            i = a - ramp + k
            if 0 <= i < len(env): env[i] = min(env[i], floor + (1 - floor) * (1 - k / ramp))
            i = b + k
            if 0 <= i < len(env): env[i] = min(env[i], floor + (1 - floor) * (k / ramp))
    return env


def _compose_old(sheet, series_id, speech=(), music_gain=0.5, sfx_gain=0.7):
    total = float(sheet["beats"][-1]["t_end"])
    buf = array.array("f", [0.0]) * int(total * SR + SR)
    th = theme(series_id); rnd = random.Random(seed_of(series_id) ^ 7)
    music = array.array("f", [0.0]) * len(buf); sfx = array.array("f", [0.0]) * len(buf)
    for b in sheet["beats"]:
        t0, t1 = float(b["t_start"]), float(b["t_end"])
        v, a = mood(b)
        scale = MAJOR if v >= 0.2 else MINOR
        bpm = 78 + 52 * max(0.0, min(1.0, a)); step = 60.0 / bpm / 2
        root = th["root"] + (0 if v >= 0.2 else -2)
        t, i = t0, 0
        while t < t1 - 0.05:
            deg = th["motif"][i % 4] if i % 8 < 4 else (th["motif"][i % 4] + 2) % 5
            note = root + 12 + scale[deg]
            _add(music, t + (th["swing"] if i % 2 else 0), pluck(hz(note)), 0.30)
            if i % 4 == 0:
                _add(music, t, pad(hz(root - 12 + scale[th["motif"][0]]), min(step * 4, t1 - t)), 0.22)
            t += step; i += 1
        act = str(b.get("action", "")).lower()
        placed = set()
        for keys, kind in SFX_RULES:
            if kind not in placed and any(k in act for k in keys):
                placed.add(kind)
                w = sfx_wave(kind, rnd)
                if kind in ("run", "step"):
                    tt = t0 + 0.5
                    while tt < min(t1, t0 + 4.0):
                        _add(sfx, tt, w, 0.55); tt += 0.28 if kind == "run" else 0.5
                else:
                    _add(sfx, t0 + 0.4, w, 0.8)
    env = duck_envelope(total, speech)
    out = array.array("h", [0]) * len(buf)
    for k in range(len(buf)):
        x = (music[k] * music_gain * env[k] + sfx[k] * sfx_gain)
        out[k] = int(max(-1.0, min(1.0, x)) * 20000)
    return out


def compose(sheet, series_id, speech=(), music_gain=0.55, sfx_gain=0.7):
    """Yeni skor motoru (score_engine: besteli tema, akorlar, ritim, yankı) + eylem efektleri. numpy yoksa eski üretici."""
    try:
        import numpy as np
        import score_engine as se
    except ImportError:
        return _compose_old(sheet, series_id, speech, music_gain, sfx_gain)
    music = se.compose(sheet, series_id, speech)
    sfx = np.zeros(len(music), dtype=np.float32); rnd = random.Random(seed_of(series_id) ^ 7)
    for b in sheet["beats"]:
        t0, t1 = float(b["t_start"]), float(b["t_end"]); act = str(b.get("action", "")).lower(); placed = set()
        for keys, kind in SFX_RULES:
            if kind in placed or not any(k in act for k in keys): continue
            placed.add(kind); w = np.array(sfx_wave(kind, rnd), dtype=np.float32)
            if not len(w): continue
            tts = [t0 + 0.5 + i * (0.28 if kind == "run" else 0.5) for i in range(int(3.5 / (0.28 if kind == "run" else 0.5)))] if kind in ("run", "step") else [t0 + 0.4]
            for tt in tts:
                if tt >= t1: break
                i0 = int(tt * SR); n_ = min(len(w), len(sfx) - i0)
                if n_ > 0: sfx[i0:i0 + n_] += w[:n_] * (0.5 if kind in ("run", "step") else 0.8)
    x = music * music_gain + sfx * sfx_gain * 0.6
    return (np.clip(x, -1, 1) * 20000).astype("<i2")


def write_wav(path, samples):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(samples.tobytes())


def speech_intervals(episode_dir):
    vm = os.path.join(episode_dir, "voice_manifest.json")
    if not os.path.exists(vm): return []
    import shot_planner as sp
    items = sp.assign_offsets(json.load(open(vm, encoding="utf-8"))["items"])
    return [(float(i.get("start_s", 0)), float(i.get("start_s", 0)) + float(i.get("duration_s", 0))) for i in items]


def run(episode_dir, series_id):
    sheet = json.load(open(os.path.join(episode_dir, "beat_sheet.json"), encoding="utf-8"))
    sp_iv = speech_intervals(episode_dir)
    samples = compose(sheet, series_id, sp_iv)
    path = os.path.join(episode_dir, "audio", "bed.wav")
    write_wav(path, samples)
    man = {"status": "PASSED", "bed": path, "seconds": round(len(samples) / SR, 1), "theme": theme(series_id),
           "licence": "kodla üretildi, telifsiz", "cost_eur": 0}
    json.dump(man, open(os.path.join(episode_dir, "audio", "music_manifest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return man


def mix(episode_dir, dialogue_wav):
    """Diyalog zaman çizelgesi + müzik/efekt yatağı -> tek wav. Yatak yoksa diyalog olduğu gibi döner."""
    bed = os.path.join(episode_dir, "audio", "bed.wav")
    if not os.path.exists(bed) or not os.path.exists(dialogue_wav):
        return dialogue_wav
    out = os.path.join(episode_dir, "animatic", "timeline_mix.wav")
    ff = shutil.which("ffmpeg") or "ffmpeg"
    r = subprocess.run([ff, "-y", "-loglevel", "error", "-i", dialogue_wav, "-i", bed, "-filter_complex",
                        "[0:a]aresample=44100,aformat=channel_layouts=mono[a];[1:a]aresample=44100,aformat=channel_layouts=mono[b];"
                        "[a][b]amix=inputs=2:duration=first,volume=2[m]", "-map", "[m]", "-ac", "2", "-ar", "44100", out],
                       capture_output=True, text=True)
    return out if r.returncode == 0 and os.path.exists(out) else dialogue_wav


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--episode-dir", required=True); ap.add_argument("--series-id", required=True)
    a = ap.parse_args(); print(json.dumps(run(a.episode_dir, a.series_id), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
