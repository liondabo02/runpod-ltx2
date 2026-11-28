"""AHOS dinleyici tepkisi (diziden bağımsız, saf Python): tepki planının ZAMANI, KİME kesileceği ve dinleyenin NE oynayacağı.

Tepki planı yalnız kamerayı dinleyene çevirmek değildir: dinleyen konuşana bakar, replikin duygusuna karşılık gelen yüzü takınır ve
küçük bir baş hareketiyle karşılık verir. Karar verisi planın kendisidir (replikler, replikin duygu etiketi, yönetmen bakışı);
proje kimliği ya da sahne koordinatı kullanılmaz."""
import math

REACT_AFTER = 1.0        # replik bittikten sonra dinleyende kalma süresi (sn)
REACT_MID = 0.9          # uzun replikin ortasında tepki süresi (sn)
REACT_MIN_LINE = 3.0     # bu süreden uzun replikte orta tepki
MID_AT = 0.62            # orta tepkinin replik içindeki yeri (oran)
MIN_SHOT_S = 0.6         # bundan kısa tepki planı kesilmez (göz yakalayamaz, titreme gibi okunur); araya bundan kısa dönüş de bırakılmaz

ONSET_S, RAMP_S = 0.12, 0.20      # kesmeden sonra yüz kısa bir an sonra değişir: değişim planın içinde görülür
TAIL_S = 0.35                     # plan bittikten sonra ifade/baş bu sürede bırakılır
NOD_S, NOD = 0.45, 0.55           # onay baş hareketi (poz 'head[0]' birimi)
TURN = 0.7                        # konuşana baş dönüşü (replik sürerken dinleyenin dönüşüyle aynı)
BROW = 0.45                       # kaş kalkışı

# replikin duygusu -> dinleyenin karşılığı
RESPONSE = {"happy": "happy", "laugh": "happy", "surprise": "surprise", "curious": "curious",
            "sad": "sad", "angry": "sad", "sly": "curious", "neutral": "curious"}


def listener_of(beat, speaker):
    """Repliki kim dinliyor: yönetmen bakışında konuşanın baktığı oyuncu; yoksa kadrodaki ilk diğer oyuncu."""
    others = [c for c in beat.get("cast") or [] if c != speaker]
    if not others:
        return None
    gz = ((beat.get("choreo") or {}).get("gaze") or {}).get(speaker)
    return gz if gz in others else others[0]


def _speaking(lines, a, b):
    """(a, b) aralığıyla çakışan ilk replikin başlangıcı (yoksa None)."""
    starts = [max(a, l["start"]) for l in lines if l["start"] < b and l["end"] > a]
    return min(starts) if starts else None


def windows(beat):
    """Vuruşun tepki pencereleri (mutlak sn): [{'t0','t1','listener','speaker','mood'}], zaman sırasıyla, çakışmasız.
    Kaynaklar: replik bittikten sonraki sessizlik ve uzun replikin ortası. Kısa aralıklı aynı dinleyici pencereleri birleşir
    (konuşana MIN_SHOT_S'den kısa dönüş olmaz); sonunda MIN_SHOT_S'den kısa kalan pencere atılır (anlık kesme olmaz)."""
    cast, lines = beat.get("cast") or [], beat.get("lines") or []
    if len(cast) < 2 or not lines:
        return []
    beat_end = float(beat.get("t_end", math.inf))
    raw = []
    for ln in sorted(lines, key=lambda l: l["start"]):
        who = listener_of(beat, ln["char"])
        if who is None:
            continue
        row = {"listener": who, "speaker": ln["char"], "mood": ln.get("mood", "neutral")}
        d = ln["end"] - ln["start"]
        if d >= REACT_MIN_LINE:
            a = ln["start"] + MID_AT * d
            raw.append(dict(row, t0=a, t1=min(a + REACT_MID, beat_end)))
        a, b = ln["end"], min(ln["end"] + REACT_AFTER, beat_end)
        nxt = _speaking(lines, a, b)                          # sıradaki replik başlayınca kamera konuşana döner
        b = b if nxt is None else nxt
        if b > a:
            raw.append(dict(row, t0=a, t1=b))
    out = []
    for w in sorted(raw, key=lambda w: w["t0"]):
        if out and w["t0"] - out[-1]["t1"] < MIN_SHOT_S:
            last = out[-1]
            between = [l for l in lines if l["start"] < w["t0"] and l["end"] > last["t1"] and l["char"] != last["speaker"]]
            if w["listener"] == last["listener"] and not between:
                last["t1"] = max(last["t1"], w["t1"])
                continue
            w = dict(w, t0=max(w["t0"], last["t1"]))
        if w["t1"] > w["t0"]:
            out.append(w)
    return [w for w in out if w["t1"] - w["t0"] >= MIN_SHOT_S - 1e-9]


def camera_windows(beat, blocked=()):
    """Kameranın gerçekten dinleyene kesileceği pencereler. blocked: [(a, b)] mutlak sn; bu aralıklarda kadraj başka motorundur
    (temas anının sabit aksiyon kadrajı). Kalan parça MIN_SHOT_S'den kısaysa kesme yapılmaz (anlık plan olmaz)."""
    out = []
    for w in windows(beat):
        pieces = [(w["t0"], w["t1"])]
        for a, b in blocked:
            pieces = [q for p0, p1 in pieces for q in ((p0, min(p1, a)), (max(p0, b), p1)) if q[1] > q[0]]
        out += [dict(w, t0=p0, t1=p1) for p0, p1 in pieces if p1 - p0 >= MIN_SHOT_S - 1e-9]
    return out


def target(beat, t, blocked=()):
    """Tepki planında kamera kimde olmalı (yoksa None)."""
    return next((w["listener"] for w in camera_windows(beat, blocked) if w["t0"] <= t < w["t1"]), None)


def _smooth(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def performance(beat, cid, t):
    """t anında cid'in dinleyici oyunculuğu ya da None.
    {'speaker', 'weight' 0..1 (bakış/baş dönüşü), 'emotion' (ifade henüz başlamadıysa None), 'brow', 'nod'}."""
    for w in windows(beat):
        if w["listener"] != cid or not (w["t0"] <= t < w["t1"] + TAIL_S):
            continue
        if any(l["char"] == cid and l["start"] <= t < l["end"] for l in beat.get("lines") or []):
            return None                                       # dinleyen söze girdi: artık kendi replikini oynar
        u = t - w["t0"]
        release = 1.0 if t < w["t1"] else _smooth(1.0 - (t - w["t1"]) / TAIL_S)
        rise = _smooth((u - ONSET_S) / RAMP_S)
        k = rise * release
        n = (u - ONSET_S) / NOD_S
        return {"speaker": w["speaker"], "weight": _smooth(u / RAMP_S) * release,
                "emotion": RESPONSE.get(w["mood"], "curious") if u >= ONSET_S and release > 0.5 else None,
                "brow": BROW * k, "nod": NOD * math.sin(math.pi * n) * release if 0.0 < n < 1.0 else 0.0}
    return None
