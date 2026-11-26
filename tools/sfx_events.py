"""Temas olaylarından efekt (SFX) üretimi. Aynı olay kaynağı (object_state.events) hem görüntüde hem seste kullanılır: ses motoru tahmin etmez.
Her olay TEK kez: kimlik = sha1(bölüm|nesne|tür|zaman). Yeniden çalıştırma/yeniden başlatmada aynı kimlik aynı ses, mükerrer üretilmez.
Efektler kodla sentezlenir (üçüncü taraf varlık yok, telif sorunu yok): kaynak kaydı cue dosyasında."""
import hashlib, json, math, os, random
import object_state as O

SR = 22050
MATERIAL = {"bottle": "glass", "lantern": "glass", "stone": "hard", "shovel": "metal", "mic": "metal"}
PROVENANCE = "AHOS kod ile sentez (sfx_events.py); üçüncü taraf ses varlığı yok; telif/lisans sorunu yok"


def kind_for(etype, prop):
    mat = MATERIAL.get(prop, "soft")
    if etype == "dispose":
        return "clunk"
    if mat == "glass":
        return "clink"
    if etype == "drop":
        return "thud" if mat in ("hard", "metal") else "tap"
    return "tap"


def _cid(episode, beat_key, prop, etype, t):
    return hashlib.sha1(f"{episode}|{beat_key}|{prop}|{etype}|{t:.3f}".encode()).hexdigest()[:12]


def cues_from_beats(sheet, episode="ep"):
    """Beat sheet'ten temas SFX cue listesi (mutlak zaman). Her nesne olayı için tam bir cue."""
    cues = {}
    for bi, b in enumerate(sheet.get("beats", [])):
        t0 = float(b.get("t_start", 0.0)); key = b.get("id") or f"b{bi}"
        for oi, ob in enumerate((b.get("choreo") or {}).get("objects", [])):
            tr = ob.get("track") or []
            if not tr:
                continue
            w = O.weight_of(ob.get("prop"))
            for e in O.events(tr):
                t = t0 + float(e["t"])
                cid = _cid(episode, f"{key}#{oi}", ob.get("prop"), e["type"], t)
                cues[cid] = {"id": cid, "t": round(t, 3), "type": e["type"], "prop": ob.get("prop"), "kind": kind_for(e["type"], ob.get("prop")),
                             "gain": round(0.35 + 0.25 * min(1.0, w / 2.0), 3), "beat": key, "source": "object_state.events"}
    return sorted(cues.values(), key=lambda c: (c["t"], c["id"]))


def wave(kind, seed):
    """Deterministik dalga biçimi (aynı kimlik -> aynı örnekler)."""
    rnd = random.Random(seed)
    if kind == "tap":
        n = int(SR * 0.06); return [((rnd.random() * 2 - 1) * 0.6 + math.sin(2 * math.pi * 900 * k / SR) * 0.4) * math.exp(-k / (SR * 0.012)) for k in range(n)]
    if kind == "clink":
        n = int(SR * 0.22); return [(math.sin(2 * math.pi * 2400 * k / SR) * 0.6 + math.sin(2 * math.pi * 3150 * k / SR) * 0.4) * math.exp(-k / (SR * 0.05)) for k in range(n)]
    if kind == "thud":
        n = int(SR * 0.16); return [(math.sin(2 * math.pi * 95 * k / SR) * 0.8 + (rnd.random() * 2 - 1) * 0.2 * math.exp(-k / (SR * 0.01))) * math.exp(-k / (SR * 0.05)) for k in range(n)]
    if kind == "clunk":
        n = int(SR * 0.28); return [(math.sin(2 * math.pi * 210 * k / SR) * 0.6 + math.sin(2 * math.pi * 333 * k / SR) * 0.4) * math.exp(-k / (SR * 0.08)) for k in range(n)]
    return []


def render(cues, n_samples):
    """Cue listesini bir tampona yazar (numpy). Kimliğe göre tekilleştirilir: aynı cue iki kez eklenmez."""
    import numpy as np
    buf = np.zeros(n_samples, dtype=np.float32); seen = set()
    for c in cues:
        if c["id"] in seen:
            continue
        seen.add(c["id"])
        w = np.array(wave(c["kind"], int(c["id"], 16)), dtype=np.float32)
        i0 = int(c["t"] * SR); n = min(len(w), n_samples - i0)
        if n > 0 and i0 >= 0:
            buf[i0:i0 + n] += w[:n] * c["gain"]
    return buf


def write_manifest(path, cues):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump({"provenance": PROVENANCE, "count": len(cues), "cues": cues}, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
