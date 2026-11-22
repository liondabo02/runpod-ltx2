"""AHOS çekim hareket mantığı (saf Python, Blender'dan bağımsız; testlenebilir).

Bir vuruşun eylem metninden her karakter için hareket türü seçer, zamana bağlı poz üretir.
Açı konvansiyonu (mesh_factory yüzü -Y'ye bakar):
  kol/bacak 'rx' negatif = ileri; kol 'ry' dışarı: sağ(R) -a, sol(L) +a;
  kafa rx pozitif = öne eğ; root lean pozitif = öne eğil; yaw pozitif = -Y'den +X'e dön.
"""
import math, re

W = 2 * math.pi

KINDS = [  # öncelik sırasıyla (ilk eşleşen kazanır)
    ("run", r"koş|kaç|fırla|süzül\w* hız"),
    ("jump", r"zıpla|atla|sıçra|hoplay"),
    ("dance", r"dans|dönüp|dön(er|erek|üyor)|sallan"),
    ("wave", r"salla|selam|karşıla|el sal"),
    ("laugh", r"gül|kahkaha|eğlen|neşe"),
    ("surprise", r"şaşır|ürk|korku|hayret|irkil|aniden"),
    ("sit", r"otur|çömel"),
    ("reach", r"kaldır|topla|uzan|koy(ar|up|du)|sula|al(ır|ıp|dı|arak)\b|tut(ar|up|ar)|yakal|çek(er|ip)|kaz|dök|ek(er|ip|ti)\b|çukur|eğil|uzat|göster|işaret"),
    ("look", r"ara(r|rlar|ken|yıp|mak)?\b|bak|gör|keşfet|incele|dinle|izle"),
    ("walk", r"yürü|git|gider|gel|yaklaş|ilerle|in(er|ip)\b|dolaş|takip|çık|geç|tırman|süzül|yuvarlan|peşin"),
]
KIND_RE = [(k, re.compile(p, re.I)) for k, p in KINDS]
SPEED = {"run": 3.0, "walk": 1.6}


def classify(text):
    t = (text or "").lower()
    for kind, rx in KIND_RE:
        if rx.search(t):
            return kind
    return "idle"


def clauses(text):
    return [c.strip() for c in re.split(r"[.;!?]|,| ve | ama | sonra ", text or "") if c.strip()]


def motion_for(char, action, char_name=None, seed=0):
    """Eylem metninde karakterin adı geçen cümleciğe göre hareket türü; yoksa genel eylem."""
    key = (char_name or char or "").lower()[:3]
    if key:
        for c in clauses(action):
            if key in c.lower():
                k = classify(c)
                if k != "idle":
                    return k
    k = classify(action)
    return k


def smooth(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def slots(n, spread=1.25):
    if n <= 1:
        return [0.0]
    return [round((i - (n - 1) / 2.0) * spread, 3) for i in range(n)]


def move_target(kind, x0, seed):
    d = 1.0 if (seed % 2 == 0) else -1.0
    dist = {"walk": 1.8, "run": 2.9}.get(kind, 0.0)
    x1 = x0 + d * dist
    if abs(x1) > 1.9:
        x1 = x0 - d * dist
    return max(-1.9, min(1.9, x1))


def base_pose(x=0.0):
    return {"x": x, "y": 0.0, "z": 0.0, "yaw": 0.0, "lean": 0.0,
            "head": [0.0, 0.0, 0.0], "aL": [0.0, 0.0], "aR": [0.0, 0.0], "lL": 0.0, "lR": 0.0}


def arm_out(p, side, a):
    (p["aL"] if side == "L" else p["aR"])[1] = (a if side == "L" else -a)


def arm_fwd(p, side, a):
    (p["aL"] if side == "L" else p["aR"])[0] = -a


def pose_at(kind, t, dur, seed, x0, x1, H, hip_z, speaking=False):
    p = base_pose(x0)
    ph = 0.0 if dur <= 0 else min(1.0, max(0.0, t / dur))
    s = (seed % 7) * 0.9
    for side in "LR":
        arm_out(p, side, 0.10 + 0.03 * math.sin(W * 0.4 * t + s))
    p["z"] = 0.012 * H * abs(math.sin(W * 0.9 * t + s))
    p["head"][2] = 0.25 * math.sin(W * 0.35 * t + s)
    p["head"][1] = 0.10 * math.sin(W * 0.5 * t + s * 1.3)
    p["yaw"] = 0.12 * math.sin(W * 0.2 * t + s)
    p["lean"] = 0.03 * math.sin(W * 0.45 * t + s)
    for side, sg in (("L", 1), ("R", -1)):
        arm_fwd(p, side, 0.25 * (0.5 + 0.5 * math.sin(W * 0.7 * t + s + sg)))

    if kind in ("walk", "run"):
        f = SPEED[kind]; amp = 0.5 if kind == "walk" else 0.95
        mv = smooth(ph / 0.85)
        p["x"] = x0 + (x1 - x0) * mv
        direction = 1.0 if x1 >= x0 else -1.0
        moving = ph < 0.85
        p["yaw"] = direction * (0.75 if moving else 0.2)
        sw = math.sin(W * f * t) if moving else 0.0
        p["lL"], p["lR"] = -amp * sw, amp * sw
        for side, sg in (("L", 1), ("R", -1)):
            arm_fwd(p, side, sg * amp * 0.7 * sw + (0.5 if kind == "run" else 0.0))
            arm_out(p, side, 0.12)
        p["z"] = abs(sw) * (0.02 if kind == "walk" else 0.07) * H
        p["lean"] = 0.04 if kind == "walk" else 0.20
    elif kind == "wave":
        arm_out(p, "R", 2.4 + 0.35 * math.sin(W * 2.5 * t))
        p["head"][1] = 0.12; p["yaw"] = 0.15 * math.sin(W * 0.3 * t)
    elif kind == "jump":
        j = max(0.0, math.sin(math.pi * ph * 3))
        p["z"] = 0.22 * H * j
        a = 2.5 if j > 0.1 else 0.3
        arm_out(p, "L", a); arm_out(p, "R", a)
        p["lL"] = p["lR"] = 0.25 * j
    elif kind == "dance":
        p["z"] = 0.03 * H * abs(math.sin(W * 2 * t))
        p["yaw"] = 0.5 * math.sin(W * 1.0 * t)
        arm_out(p, "L", 1.4 + 0.8 * math.sin(W * 1.0 * t)); arm_out(p, "R", 1.4 - 0.8 * math.sin(W * 1.0 * t))
        p["lL"] = 0.3 * math.sin(W * 2 * t); p["lR"] = -p["lL"]
        p["head"][1] = 0.25 * math.sin(W * 1.0 * t)
    elif kind == "laugh":
        p["z"] = 0.015 * H * math.sin(W * 6 * t)
        p["head"][0] = -0.3; p["lean"] = -0.08
        arm_fwd(p, "L", 0.5); arm_fwd(p, "R", 0.5)
    elif kind == "surprise":
        k = math.exp(-3.0 * t)
        p["z"] = 0.12 * H * k
        arm_out(p, "L", 0.3 + 1.6 * k); arm_out(p, "R", 0.3 + 1.6 * k)
        p["head"][0] = -0.15 * k; p["lean"] = -0.12 * k
    elif kind == "sit":
        sit = smooth(ph / 0.2)
        p["z"] = -max(0.0, hip_z - 0.06 * H) * sit
        p["lL"] = p["lR"] = -1.45 * sit
        arm_fwd(p, "L", 0.4 * sit); arm_fwd(p, "R", 0.4 * sit)
    elif kind == "reach":
        b = math.sin(math.pi * smooth(ph))
        p["lean"] = 0.38 * b
        arm_fwd(p, "L", 1.2 * b); arm_fwd(p, "R", 1.2 * b)
        p["head"][0] = 0.25 * b
    elif kind == "look":
        p["head"][2] = 0.9 * math.sin(W * 0.4 * t + s)
        p["head"][0] = 0.18; p["lean"] = 0.12 + 0.05 * math.sin(W * 0.8 * t)
        p["x"] = x0 + 0.6 * math.sin(W * 0.12 * t + s)
        v = 0.6 * W * 0.12 * math.cos(W * 0.12 * t + s)
        sw = math.sin(W * 1.8 * t) * min(0.6, abs(v) * 1.2)
        p["lL"], p["lR"] = -sw, sw
        arm_fwd(p, "L", 0.6 + 0.3 * math.sin(W * 0.9 * t)); arm_out(p, "R", 0.5)
        p["yaw"] = 0.5 * (1 if v > 0 else -1)
    # konuşurken doğal el/baş hareketi (yalnız sakin türlerde)
    if speaking and kind in ("idle", "look", "wave", "sit"):
        g = 0.5 + 0.5 * math.sin(W * 1.7 * t + s)
        p["head"][0] += 0.07 * math.sin(W * 3 * t)
        if kind != "wave":
            arm_fwd(p, "R", 0.9 * g); arm_out(p, "R", 0.35 + 0.5 * g)
        p["z"] += 0.02 * H * max(0.0, math.sin(W * 2.3 * t))
    # canlılık katmanı: bekleyen karakter de yaşar (ağırlık kaydırma, ara sıra jest, merak)
    if kind in ("idle", "look", "sit"):
        slot = int(t // 3.2); loc = (t % 3.2) / 3.2
        h = ((slot * 2654435761 + seed * 40503) & 0xFFFF) / 65535.0
        bump = math.sin(math.pi * min(1.0, loc / 0.45)) if loc < 0.45 else 0.0
        if kind != "sit":
            p["x"] += 0.10 * math.sin(W * 0.11 * t + s) * (H / 1.0) * 0.5   # ağırlık kaydırma
        if h > 0.55:                                  # jest: el kaldır / kol salla
            side = "R" if h > 0.78 else "L"
            arm_out(p, side, 0.35 + 1.1 * bump); arm_fwd(p, side, 0.5 * bump)
            p["head"][2] += 0.3 * bump * (1 if h > 0.78 else -1)
        elif h < 0.2:                                 # kafa eğ, düşün
            p["head"][2] += 0.35 * bump; p["lean"] += 0.05 * bump
        p["z"] += 0.01 * H * max(0.0, math.sin(W * 1.3 * t + s))
    return p


VISEME_OPEN = {"X": 0.05, "A": 0.12, "B": 0.40, "C": 0.85, "D": 1.0, "E": 0.65, "F": 0.35, "G": 0.30, "H": 0.60}


def mouth_open(cues, t_in_line):
    for c in cues:
        if c[0] <= t_in_line < c[1]:
            return c[2]
    return 0.05


def blink(t, seed):
    ph = (t + seed * 0.37) % 3.6
    return 1.0 if ph < 0.12 else 0.0


CAMS = {"wide": (5.2, 1.2, 0.85, 30.0), "medium": (3.4, 1.0, 0.8, 35.0), "close": (2.2, 1.0, 0.8, 50.0)}


def camera_for(preset, cx, focus_h, beat_index, ph):
    dist, cz, tz, lens = CAMS.get(preset, CAMS["medium"])
    if preset == "close":
        tz = focus_h * 0.80; cz = tz + 0.05
    off = (0.5 if beat_index % 2 == 0 else -0.5) * (1.0 if preset == "wide" else 0.5)
    d = dist * (1.0 - 0.08 * ph)
    return {"loc": [cx + off, -d, cz], "target": [cx, 0.0, tz], "lens": lens}
