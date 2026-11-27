"""Yüz okunurluğu ölçüsü: göz ve kaş pikselleri saç/şapka altında kalmıyor mu? ÇİZİLEN karelerden ölçer, saç geometrisini bilmez.
Başvuru = aynı tasarımın saçsız ve aksesuarsız çizimi. Öğe maskesi = başvuru ile 'öğe çizilmemiş' başvurunun farkı.
Görünür oran = maske piksellerinden, gerçek tasarımda öğe çizilince FARK YARATANLARIN oranı: üstünü saç kapatan da, saçla aynı renkte kalıp
seçilemeyen de 'görünmüyor' sayılır.
Ölçmediği: yüz ifadesinin seyirciye anlaşılır olması, saçın estetiği, başka oyuncu/el/nesne örtmesi."""
from PIL import Image, ImageChops

import puppet2d as pp

DIFF = 28                                   # kanal farkı bunun üstündeyse piksel 'değişti' sayılır (kenar yumuşatma payı)
MIN_VISIBLE = {"eyes": 0.90, "brows": 0.90}
MIN_MASK_PX = 40                            # bundan küçük maske ölçüm değildir
EMOTIONS = ("neutral", "happy", "laugh", "surprise", "scared", "sad", "angry", "curious", "sly")
VIEWS = (("front", 0.0, 0.0), ("front_turn_r", 0.0, 0.9), ("front_turn_l", 0.0, -0.9), ("three_quarter_r", 0.55, 0.0),
         ("three_quarter_l", -0.55, 0.0), ("side_r", 0.9, 0.0), ("side_l", -0.9, 0.0))
SIZE, PPM_PX = (520, 640), 520.0            # tuval ve figür boyu (px): ölçü boydan bağımsız aynı çözünürlükte


def pose(view, yaw, head_turn):
    return {"x": 0.0, "z": 0.0, "yaw": yaw, "lean": 0.0, "sq": 1.0, "head": [0.0, 0.0, head_turn],
            "aL": [0.0, 0.1], "aR": [0.0, -0.1], "lL": 0.0, "lR": 0.0, "view": "side" if view.startswith("side") else "front"}


def render(des, p, st, t=0.0):
    cv = pp.Cv(SIZE[0], SIZE[1], ss=1)
    cv.img.paste((120, 170, 210), (0, 0, SIZE[0], SIZE[1]))
    pp.draw_character(cv, des, p, st, SIZE[0] / 2, SIZE[1] - 30, PPM_PX / des["height"], t)
    return cv.img


def _changed(a, b):
    r, g, bl = ImageChops.difference(a.convert("RGB"), b.convert("RGB")).split()
    return ImageChops.lighter(ImageChops.lighter(r, g), bl).point(lambda v: 255 if v > DIFF else 0)


def measure(des, emotion="neutral", view=("front", 0.0, 0.0), blink=0, brow=0.0, t=0.0):
    """Dönüş: {'eyes': görünür oran, 'brows': oran, 'eyes_px': n, 'brows_px': n}."""
    p = pose(*view)
    st = {"mouth": "X", "blink": blink, "emotion": emotion, "gaze": 0.0, "brow": brow, "pulse": 0.0}
    bare = dict(des, hair_style="bald", accessory="none")
    ref = render(bare, p, st, t)
    real = render(des, p, st, t)
    out = {}
    for item in ("eyes", "brows"):
        gone = dict(st, hide=(item,))
        mask = _changed(ref, render(bare, p, gone, t))                 # öğenin açık yüzdeki yeri
        seen = _changed(real, render(des, p, gone, t))                 # gerçek karede o pikselde öğe fark yaratıyor mu (örtülmemiş VE kontrastlı)
        n = mask.histogram()[255]
        out[item] = ImageChops.darker(mask, seen).histogram()[255] / n if n else 0.0
        out[item + "_px"] = n
    return out


def failures(m, limits=None):
    L = dict(MIN_VISIBLE, **(limits or {}))
    why = []
    for item in ("eyes", "brows"):
        if m[item + "_px"] < MIN_MASK_PX:
            why.append(f"{item}: ölçülecek piksel yok ({m[item + '_px']})")
        elif m[item] < L[item]:
            why.append(f"{item} görünür oranı {m[item]:.2f} < {L[item]:.2f}")
    return why


def sweep(des, emotions=EMOTIONS, views=VIEWS, blinks=(0, 1), times=(0.0,)):
    """Tüm ifade × görünüş × göz kırpma: [(anahtar, ölçüm, sorunlar)]."""
    rows = []
    for e in emotions:
        for v in views:
            for b in blinks:
                for t in times:
                    m = measure(des, e, v, blink=b, t=t)
                    rows.append(((e, v[0], b, t), m, failures(m)))
    return rows


# ---------------------------------------------------------------- üretim kapısı: bölümde oynayan HER tasarım (gerçek spec değerleriyle)
GATE_EMOTIONS = ("neutral", "happy", "laugh", "surprise")
GATE_VIEWS = tuple(v for v in VIEWS if v[0] in ("front", "front_turn_l", "three_quarter_r", "side_r", "side_l"))


def check_designs(designs, ids):
    """Dönüş: {kimlik: {'checked': n, 'worst': {'eyes': oran, 'brows': oran}, 'fails': [{'emotion','view','why'}]}}.
    Tasarım ölçüsüdür: sahnedeki başka oyuncu/nesne örtmesini ve kadrajı ölçmez."""
    out = {}
    for cid in sorted(ids):
        rows = sweep(designs[cid], emotions=GATE_EMOTIONS, views=GATE_VIEWS, blinks=(0,))
        out[cid] = {"checked": len(rows), "worst": {k: round(min(m[k] for _key, m, _w in rows), 3) for k in ("eyes", "brows")},
                    "fails": [{"emotion": key[0], "view": key[1], "why": why} for key, _m, why in rows if why]}
    return out


def problems(report):
    return [{"rule": "FACE_UNREADABLE", "engine": "character_drawing", "character": cid,
             "why": f"{len(r['fails'])}/{r['checked']} bileşimde yüz okunmuyor; ilk: {r['fails'][0]['emotion']} {r['fails'][0]['view']}: {'; '.join(r['fails'][0]['why'])}"}
            for cid, r in report.items() if r["fails"]]
