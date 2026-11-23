"""AHOS nesne (prop) çizimi: sahne metninde geçen önemli nesneleri kalın konturlu düz renkli çizer (saf Python/Pillow)."""
import math, re

INK = (38, 30, 42)
RULES = [("seed", r"tohum|çekirdek|ışık veren"), ("stone", r"\btaş|\btas\b|kaya"), ("hat", r"şapka|hasır"),
         ("flower", r"çiçek|tomurcuk|filiz|fidan"), ("bottle", r"şişe|kavanoz"), ("drops", r"damla|yağmur|su\b"),
         ("leaves", r"yaprak|rüzgâr|rüzgar"), ("shovel", r"kürek|küreği"),
         ("mic", r"mikrofon|stand-?up|sahne"), ("balloon", r"balon"), ("lantern", r"fener|lamba"), ("kite", r"uçurtma|ucurtma")]
RX = [(k, re.compile(p, re.I)) for k, p in RULES]


def extract(text, limit=2):
    out = []
    for k, rx in RX:
        if rx.search(text or "") and k not in out:
            out.append(k)
    return out[:limit]


def _o(cam, ow=None):
    return ow or max(1.6, 0.012 * cam.s)


def draw(cv, cam, kind, wx, wy, t, k=0):
    ow = _o(cam); s = cam.s
    x, y = cam.x(wx), cam.y(wy)
    if kind == "seed":
        pulse = 0.5 + 0.5 * math.sin(t * 4 + k)
        cv.ellipse(x, y, (0.30 + 0.06 * pulse) * s, (0.30 + 0.06 * pulse) * s, (255, 245, 170), None, 0)
        cv.ellipse(x, y, 0.15 * s, 0.15 * s, (255, 214, 70), INK, ow)
        cv.ellipse(x - 0.04 * s, y - 0.05 * s, 0.04 * s, 0.04 * s, (255, 255, 255), None, 0)
        for i in range(5):
            a = t * 1.5 + i * 1.26
            cv.ellipse(x + math.cos(a) * 0.3 * s, y + math.sin(a) * 0.3 * s, 0.025 * s, 0.025 * s, (255, 255, 255), None, 0)
    elif kind == "stone":
        cv.ellipse(x, y, 0.30 * s, 0.20 * s, (150, 150, 160), INK, ow)
        cv.ellipse(x - 0.08 * s, y - 0.05 * s, 0.10 * s, 0.06 * s, (190, 190, 200), None, 0)
    elif kind == "hat":
        cv.ellipse(x, y, 0.42 * s, 0.10 * s, (238, 200, 110), INK, ow)
        cv.ellipse(x, y - 0.09 * s, 0.22 * s, 0.17 * s, (248, 214, 128), INK, ow)
        cv.poly([(x - 0.22 * s, y - 0.05 * s), (x + 0.22 * s, y - 0.05 * s), (x + 0.22 * s, y - 0.01 * s), (x - 0.22 * s, y - 0.01 * s)], (214, 90, 90), None, 0)
    elif kind == "flower":
        sway = math.sin(t * 2 + k) * 0.04 * s
        cv.line([(x, y + 0.55 * s), (x + sway, y)], (70, 150, 70), max(3, int(ow * 1.6)))
        cv.ellipse(x - 0.14 * s, y + 0.3 * s, 0.12 * s, 0.06 * s, (90, 180, 80), INK, ow * 0.7)
        for i in range(6):
            a = i * 1.047
            cv.ellipse(x + sway + math.cos(a) * 0.13 * s, y + math.sin(a) * 0.13 * s, 0.09 * s, 0.09 * s, (255, 130, 160), INK, ow * 0.7)
        cv.ellipse(x + sway, y, 0.08 * s, 0.08 * s, (255, 220, 80), INK, ow * 0.7)
    elif kind == "bottle":
        cv.poly([(x - 0.11 * s, y), (x + 0.11 * s, y), (x + 0.11 * s, y - 0.34 * s), (x - 0.11 * s, y - 0.34 * s)], (170, 225, 240), INK, ow)
        cv.poly([(x - 0.05 * s, y - 0.34 * s), (x + 0.05 * s, y - 0.34 * s), (x + 0.05 * s, y - 0.5 * s), (x - 0.05 * s, y - 0.5 * s)], (170, 225, 240), INK, ow)
        cv.poly([(x - 0.06 * s, y - 0.5 * s), (x + 0.06 * s, y - 0.5 * s), (x + 0.06 * s, y - 0.56 * s), (x - 0.06 * s, y - 0.56 * s)], (190, 120, 80), INK, ow)
    elif kind == "drops":
        for i in range(6):
            dx = ((i * 0.37 + k) % 1.0 - 0.5) * 1.6
            dy = 1.6 - ((t * 0.9 + i * 0.31) % 1.0) * 1.6
            cv.ellipse(cam.x(wx + dx), cam.y(dy), 0.035 * s, 0.06 * s, (120, 190, 255), INK, ow * 0.5)
    elif kind == "leaves":
        for i in range(7):
            lx = ((t * 0.9 + i * 0.7) % 6.0) - 3.0 + wx
            ly = 1.95 + 0.35 * math.sin(t * 2 + i) + i * 0.08            # başların üstünde süzülür, yüzleri kapatmaz
            cv.ellipse(cam.x(lx), cam.y(ly), 0.09 * s, 0.045 * s, (110 + i * 12, 190, 90), INK, ow * 0.5)
    elif kind == "mic":
        cv.line([(x, y - 0.95 * s), (x, y + 0.05 * s)], (90, 90, 100), max(3, int(ow * 1.6)))
        cv.ellipse(x, y + 0.08 * s, 0.22 * s, 0.05 * s, (70, 70, 80), INK, ow)
        cv.ellipse(x, y - 1.0 * s, 0.09 * s, 0.11 * s, (50, 50, 58), INK, ow)
    elif kind == "balloon":
        sway = math.sin(t * 2 + k) * 0.06 * s
        cv.line([(x, y), (x + sway, y - 0.5 * s)], INK, max(2, int(ow * 0.8)))
        cv.ellipse(x + sway, y - 0.8 * s, 0.24 * s, 0.3 * s, (235, 80, 100), INK, ow)
        cv.ellipse(x + sway - 0.08 * s, y - 0.9 * s, 0.05 * s, 0.07 * s, (255, 200, 205), None, 0)
    elif kind == "lantern":
        g = 0.5 + 0.5 * math.sin(t * 5 + k)
        cv.ellipse(x, y, (0.3 + 0.05 * g) * s, (0.3 + 0.05 * g) * s, (255, 240, 170), None, 0)
        cv.poly([(x - 0.1 * s, y - 0.14 * s), (x + 0.1 * s, y - 0.14 * s), (x + 0.12 * s, y + 0.14 * s), (x - 0.12 * s, y + 0.14 * s)], (255, 205, 80), INK, ow)
    elif kind == "kite":
        fl = math.sin(t * 3 + k) * 0.08 * s
        cv.line([(x, y), (x + fl, y - 0.9 * s)], INK, max(2, int(ow * 0.7)))
        cv.poly([(x + fl, y - 1.5 * s), (x + fl + 0.28 * s, y - 1.2 * s), (x + fl, y - 0.85 * s), (x + fl - 0.28 * s, y - 1.2 * s)], (90, 170, 235), INK, ow)
    elif kind == "shovel":
        cv.line([(x, y - 0.6 * s), (x, y)], (150, 100, 60), max(3, int(ow * 2)))
        cv.poly([(x - 0.1 * s, y), (x + 0.1 * s, y), (x + 0.07 * s, y + 0.22 * s), (x - 0.07 * s, y + 0.22 * s)], (190, 190, 200), INK, ow)


def place(kind, xs, heights, t, lt, dur):
    """Nesnenin dünya konumu (wx, wy). xs: karakter x'leri."""
    cx = sum(xs) / len(xs) if xs else 0.0
    h = max(heights) if heights else 1.1
    ph = lt / max(dur, 0.1)
    return {"seed": (cx + 0.15 * math.sin(t * 1.3), h * (0.62 + 0.12 * math.sin(t * 2.0))),
            "stone": (cx + 0.9, -0.05), "hat": (cx + 1.6 * (ph - 0.5) * 2, h * 1.25 + 0.15 * math.sin(t * 5)),
            "flower": (cx - 0.7, 0.0), "bottle": (cx + 0.35, h * 0.35), "drops": (cx, 0.0),
            "leaves": (cx, 0.0), "shovel": (cx - 0.5, 0.1),
            "mic": (cx - 0.9, 0.0), "balloon": (cx + 0.7, h * 0.75), "lantern": (cx + 0.5, h * 0.55), "kite": (cx - 0.6, h * 0.9)}.get(kind, (cx, h * 0.5))


def fx_kinds(kinds):
    out = []
    if "surprise" in kinds: out.append("burst")
    if "jump" in kinds or "dance" in kinds: out.append("stars")
    if "run" in kinds: out.append("speed")
    return out


def draw_fx(cv, cam, kind, wx, wy, t, lt):
    """Çizgi film efektleri: şaşırma patlaması, zıplama yıldızları, hız çizgileri."""
    ow = _o(cam); s = cam.s
    if kind == "burst" and lt < 1.6:
        k = min(1.0, lt / 0.25) * (1.0 - max(0.0, (lt - 1.0) / 0.6))
        se = min(s, 300.0)
        x, y = cam.x(wx) + 0.55 * se, cam.y(wy) - 0.1 * se
        pts = []
        for i in range(16):
            a = i * math.pi / 8
            r = (0.32 if i % 2 == 0 else 0.15) * se * k
            pts.append((x + math.cos(a) * r, y + math.sin(a) * r))
        cv.poly(pts, (255, 235, 70), INK, ow)
    elif kind == "stars":
        for i in range(4):
            a = t * 3 + i * 1.57
            x, y = cam.x(wx + math.cos(a) * 0.5), cam.y(wy + 0.35 + math.sin(a) * 0.2)
            r = 0.07 * s
            cv.poly([(x, y - r), (x + r * 0.3, y - r * 0.3), (x + r, y), (x + r * 0.3, y + r * 0.3), (x, y + r), (x - r * 0.3, y + r * 0.3), (x - r, y), (x - r * 0.3, y - r * 0.3)], (255, 225, 60), INK, ow * 0.5)
    elif kind == "speed":
        for i in range(6):
            yy = wy - 0.1 + i * 0.22
            xx = wx - 0.7 - ((t * 5 + i * 0.37) % 1.0) * 0.8
            cv.line([(cam.x(xx), cam.y(yy)), (cam.x(xx - 0.5), cam.y(yy))], (255, 255, 255), max(2, int(ow * 1.2)))
