"""AHOS 2D Kesme-Kukla Motoru (diziden bağımsız, saf Python + Pillow).

Vektör karakterler (büyük gözler, ifade, 9 Rhubarb ağız şekli), boyalı arka planlar, kalın kenar çizgisi.
Poz girdisi shot_motion.pose_at çıktısıdır. Her şey 'spec' ve 'sahne türü'nden üretilir; belirli bir diziye bağlı değildir.
"""
import colorsys, hashlib, math, random
from PIL import Image, ImageDraw

W, H = 1280, 720
SS = 2                      # süper-örnekleme (kenar yumuşatma)
INK = (38, 26, 40)
BASE_PPM = 250.0            # 1 metre = 250 px (geniş plan)


# ---------------------------------------------------------------- yardımcılar
def rgb(c, k=1.0):
    return tuple(max(0, min(255, int(v * 255 * k))) for v in c[:3])


def shade(col, k):
    return tuple(max(0, min(255, int(v * k))) for v in col)


def lerp(a, b, t):
    return a + (b - a) * t


class Cv:
    def __init__(self, w=W, h=H, ss=SS):
        self.ss = ss
        self.img = Image.new("RGB", (w * ss, h * ss), (255, 255, 255))
        self.d = ImageDraw.Draw(self.img)

    def P(self, pts):
        return [(x * self.ss, y * self.ss) for x, y in pts]

    def poly(self, pts, fill, ol=None, ow=3.0):
        p = self.P(pts)
        if ol is not None:
            self.d.polygon(p, fill=ol)
            self.d.line(p + [p[0]], fill=ol, width=int(ow * self.ss * 2), joint="curve")
        self.d.polygon(p, fill=fill)
        if ol is not None:
            self.d.line(p + [p[0]], fill=ol, width=max(1, int(ow * self.ss)), joint="curve")

    def ellipse(self, cx, cy, rx, ry, fill, ol=None, ow=3.0, rot=0.0, n=44):
        pts = []
        c, s = math.cos(rot), math.sin(rot)
        for i in range(n):
            a = 2 * math.pi * i / n
            x, y = rx * math.cos(a), ry * math.sin(a)
            pts.append((cx + x * c - y * s, cy + x * s + y * c))
        self.poly(pts, fill, ol, ow)

    def capsule(self, p0, p1, r0, r1, fill, ol=None, ow=3.0):
        ang = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
        nx, ny = -math.sin(ang), math.cos(ang)
        pts = [(p0[0] + nx * r0, p0[1] + ny * r0), (p1[0] + nx * r1, p1[1] + ny * r1),
               (p1[0] - nx * r1, p1[1] - ny * r1), (p0[0] - nx * r0, p0[1] - ny * r0)]
        if ol is not None:
            self.ellipse(p0[0], p0[1], r0, r0, ol, None, 0)
            self.ellipse(p1[0], p1[1], r1, r1, ol, None, 0)
            big = [(p0[0] + nx * (r0 + ow), p0[1] + ny * (r0 + ow)), (p1[0] + nx * (r1 + ow), p1[1] + ny * (r1 + ow)),
                   (p1[0] - nx * (r1 + ow), p1[1] - ny * (r1 + ow)), (p0[0] - nx * (r0 + ow), p0[1] - ny * (r0 + ow))]
            self.d.polygon(self.P(big), fill=ol)
            self.ellipse(p0[0], p0[1], r0 + ow, r0 + ow, ol, None, 0)
            self.ellipse(p1[0], p1[1], r1 + ow, r1 + ow, ol, None, 0)
        self.d.polygon(self.P(pts), fill=fill)
        self.ellipse(p0[0], p0[1], r0, r0, fill, None, 0)
        self.ellipse(p1[0], p1[1], r1, r1, fill, None, 0)

    def line(self, pts, fill, w=3.0):
        self.d.line(self.P(pts), fill=fill, width=max(1, int(w * self.ss)), joint="curve")

    def arc_pts(self, cx, cy, rx, ry, a0, a1, n=16):
        return [(cx + rx * math.cos(lerp(a0, a1, i / (n - 1))), cy + ry * math.sin(lerp(a0, a1, i / (n - 1)))) for i in range(n)]

    def done(self):
        return self.img.resize((W, H), Image.LANCZOS)


# ---------------------------------------------------------------- karakter tasarımı
def derive_design(ch, spec):
    """Bible + spec -> 2D tasarım. LLM alanları (hair_style, species, accessory) varsa onları kullanır; yoksa kurallarla türetir."""
    text = " ".join(str(ch.get(k, "")) for k in ("name", "role", "look", "personality")).lower()
    age = ch.get("age")
    try:
        age = float(age)
    except (TypeError, ValueError):
        age = 30.0
    female = bool(__import__("re").search(r"kız|kadın|anne|nine|teyze|abla|girl|woman|female|dişi", text))
    species = spec.get("species") or ("hedgehog" if __import__("re").search(r"kirpi|hedgehog", text) else "human")
    style = spec.get("hair_style")
    if not style:
        style = "spiky" if species == "hedgehog" else ("bun" if age >= 60 else ("bob" if female and age < 13 else "ponytail" if female else "short"))
    acc = spec.get("accessory") or ("glasses" if age >= 60 else "none")
    h = int(hashlib.sha256(ch["id"].encode()).hexdigest(), 16)
    pal = spec.get("palette") or {}

    def col(k, d):
        return rgb(pal[k]) if k in pal else d
    hair = col("hair", (235, 235, 240) if age >= 60 else [(70, 40, 20), (150, 100, 40), (230, 190, 80), (30, 25, 30)][h % 4])
    if species == "hedgehog":
        hair = col("hair", (120, 80, 50))
    skin = col("skin", (255, 214, 170) if species != "hedgehog" else (240, 205, 160))
    hue = (h % 360) / 360.0
    shirt = col("shirt", tuple(int(v * 255) for v in colorsys.hsv_to_rgb(hue, 0.7, 0.95)))
    shorts = col("shorts", tuple(int(v * 255) for v in colorsys.hsv_to_rgb((hue + 0.5) % 1, 0.55, 0.5)))
    accent = col("accent", tuple(int(v * 255) for v in colorsys.hsv_to_rgb((hue + 0.15) % 1, 0.8, 1.0)))
    cls = spec.get("class") or ("infant" if age < 2 else "toddler" if age < 5 else "child" if age < 13 else "adult")
    iris = (60, 40, 20) if h % 2 else (30, 60, 110)
    return {"id": ch["id"], "species": species, "hair_style": style, "accessory": acc, "hair": hair, "skin": skin,
            "shirt": shirt, "shorts": shorts, "accent": accent, "class": cls, "height": float(spec.get("height_m", 1.1)),
            "iris": iris, "female": female, "age": age}


# ---------------------------------------------------------------- ağız şekilleri (Rhubarb A-H, X)
def draw_mouth(cv, mx, my, mw, mh, letter, ol=INK):
    dark, tongue = (110, 30, 45), (235, 110, 120)
    L = letter if letter in "ABCDEFGHX" else "X"
    if L == "X":
        cv.line(cv.arc_pts(mx, my - mh * 0.4, mw * 0.5, mh * 0.55, 0.2, math.pi - 0.2), ol, 3.2); return
    if L == "A":
        cv.line([(mx - mw * 0.42, my), (mx + mw * 0.42, my)], ol, 3.6); return
    shapes = {"B": (0.50, 0.30), "C": (0.60, 0.62), "D": (0.78, 0.95), "E": (0.45, 0.55), "F": (0.26, 0.40), "G": (0.55, 0.32), "H": (0.60, 0.70)}
    ww, hh = shapes[L]
    cv.ellipse(mx, my + hh * mh * 0.3, mw * ww * 0.5, mh * hh * 0.5, dark, ol, 2.6)
    if L in ("C", "D", "H"):
        cv.ellipse(mx, my + hh * mh * 0.62, mw * ww * 0.30, mh * hh * 0.20, tongue, None, 0)
    if L in ("B", "G", "D"):
        cv.poly([(mx - mw * ww * 0.38, my + hh * mh * 0.08), (mx + mw * ww * 0.38, my + hh * mh * 0.08),
                 (mx + mw * ww * 0.34, my + hh * mh * 0.28), (mx - mw * ww * 0.34, my + hh * mh * 0.28)], (255, 255, 255), None, 0)


# ---------------------------------------------------------------- karakter çizimi
def draw_character(cv, des, pose, st, fx, fy, ppm, t=0.0):
    """fx,fy: ayak ortası (ekran px). ppm: piksel/metre. st: {'mouth':harf,'blink':0/1,'emotion':str,'dir':-1..1}"""
    Hh = des["height"] * ppm
    cls = des["class"]
    leg_h = Hh * {"infant": 0.20, "toddler": 0.24, "child": 0.28, "adult": 0.38}[cls]
    torso_h = Hh * {"infant": 0.22, "toddler": 0.25, "child": 0.27, "adult": 0.30}[cls]
    head_h = Hh - leg_h - torso_h + Hh * 0.05
    head_w = head_h * 1.12
    torso_w = Hh * {"infant": 0.30, "toddler": 0.28, "child": 0.25, "adult": 0.22}[cls]
    skin, shirt, shorts, hair = des["skin"], des["shirt"], des["shorts"], des["hair"]
    ow = max(2.2, Hh * 0.014)
    jump = pose["z"] * ppm
    sit = max(0.0, -pose["z"]) * ppm
    by = fy - jump                       # gövde tabanı (ayak) y
    squash = 1.0 + max(0.0, jump) / (Hh * 3.0) + 0.014 * math.sin(t * 2.4 + des["age"])
    pulse = float(st.get("pulse", 0.0))   # vurgu/şaşkınlıkta ezilip esneme (squash & stretch)
    if st.get("emotion") in ("surprise", "laugh"):
        pulse = max(pulse, 0.6 + 0.3 * math.sin(t * 9))
    if pulse:
        squash *= 1.0 - 0.10 * pulse
        head_h *= 1.0 + 0.12 * pulse
        head_w = head_h * 1.12
    face = max(-1.0, min(1.0, pose["head"][2] * 0.7 + pose["yaw"] * 0.55))     # bakış/dönüş yönü
    tilt = pose["head"][1] * 0.9 + pose["lean"] * 0.4
    nod = pose["head"][0]
    sway = math.sin(t * 2.2 + des["age"]) * Hh * 0.004

    # gölge
    cv.ellipse(fx, fy + Hh * 0.012, Hh * 0.30 * (1 - min(0.5, jump / (Hh * 1.5))), Hh * 0.05, shade((60, 110, 50), 0.8), None, 0)

    hip_y = by - leg_h + sit * 0.0
    torso_bot = hip_y - sit
    torso_top = torso_bot - torso_h * squash
    head_cy = torso_top - head_h * 0.40 + nod * head_h * 0.06
    hx = fx + sway + face * 0.10 * head_w

    # ---- arka saç / kirpi dikenleri / at kuyruğu
    style, species = des["hair_style"], des["species"]
    if species == "hedgehog":
        rnd = random.Random(7)
        for i in range(15):
            a = math.radians(200 + i * (140 / 14))
            r0, r1 = head_w * 0.50, head_w * (0.78 + 0.06 * (i % 2))
            c0 = (hx + math.cos(a) * r0 * 0.9, head_cy + math.sin(a) * head_h * 0.45)
            tip = (hx + math.cos(a) * r1, head_cy + math.sin(a) * head_h * 0.70)
            perp = (-math.sin(a) * head_w * 0.11, math.cos(a) * head_w * 0.11)
            cv.poly([(c0[0] + perp[0], c0[1] + perp[1]), tip, (c0[0] - perp[0], c0[1] - perp[1])], hair, INK, ow * 0.8)
        for i in range(7):    # sırt dikenleri
            sx = fx - torso_w * 0.62 + i * (torso_w * 1.24 / 6)
            cv.poly([(sx - torso_w * 0.12, torso_top + torso_h * 0.5), (sx, torso_top - torso_h * 0.05 + (i % 2) * 8), (sx + torso_w * 0.12, torso_top + torso_h * 0.5)], hair, INK, ow * 0.8)
    if style == "ponytail":
        px = hx + head_w * 0.55 + math.sin(t * 3 + 1) * head_w * 0.04
        cv.ellipse(px, head_cy + head_h * 0.18, head_w * 0.17, head_h * 0.34, hair, INK, ow, rot=-0.3)
    if style == "bob":
        cv.ellipse(hx, head_cy + head_h * 0.1, head_w * 0.60, head_h * 0.62, hair, INK, ow)

    # ---- bacaklar
    for side, sg in (("L", -1), ("R", 1)):
        swing = pose["lL"] if side == "L" else pose["lR"]
        lift = max(0.0, swing) * leg_h * 0.28
        x0 = fx + sg * torso_w * 0.24
        top = (x0, torso_bot - torso_h * 0.04)
        if sit > 1:
            foot = (x0 + sg * torso_w * 0.15, fy - Hh * 0.01 - lift)
            top = (x0, torso_bot)
        else:
            foot = (x0 + swing * leg_h * 0.22 * sg * 0.3, fy - Hh * 0.01 - lift - max(0, jump))
        cv.capsule(top, (foot[0], foot[1] - Hh * 0.03), Hh * 0.045, Hh * 0.04, skin if species != "hedgehog" else skin, INK, ow)
        cv.capsule(top, ((top[0] + foot[0]) / 2, (top[1] + foot[1]) / 2 - Hh * 0.01), Hh * 0.055, Hh * 0.05, shorts, INK, ow)
        cv.ellipse(foot[0] + sg * Hh * 0.025, foot[1], Hh * 0.075, Hh * 0.04, shade(des["accent"], 0.9), INK, ow)
    # ---- gövde
    tpts = [(fx - torso_w * 0.5, torso_top + torso_h * 0.10), (fx - torso_w * 0.36, torso_top), (fx + torso_w * 0.36, torso_top),
            (fx + torso_w * 0.5, torso_top + torso_h * 0.10), (fx + torso_w * 0.55, torso_bot), (fx - torso_w * 0.55, torso_bot)]
    cv.poly(tpts, shirt, INK, ow)
    cv.ellipse(fx, torso_top + torso_h * 0.52, torso_w * 0.13, torso_w * 0.13, des["accent"], INK, ow * 0.7)
    cv.poly([(fx - torso_w * 0.55, torso_bot - torso_h * 0.14), (fx + torso_w * 0.55, torso_bot - torso_h * 0.14),
             (fx + torso_w * 0.55, torso_bot), (fx - torso_w * 0.55, torso_bot)], shorts, None, 0)
    cv.line([(fx - torso_w * 0.55, torso_bot - torso_h * 0.14), (fx + torso_w * 0.55, torso_bot - torso_h * 0.14)], INK, ow * 0.8)
    # ---- kollar
    arm_len = Hh * 0.27
    for side, sg in (("L", -1), ("R", 1)):
        fwd, out = pose["aL"] if side == "L" else pose["aR"]
        ang = abs(out) * 1.0 if out * (1 if side == "L" else -1) >= 0 else -abs(out) * 0.4
        ang = max(-0.5, ang)
        ln = arm_len * (1.0 - 0.28 * min(1.0, abs(fwd) / 1.3))
        sh = (fx + sg * torso_w * 0.52, torso_top + torso_h * 0.14)
        hand = (sh[0] + sg * math.sin(ang) * ln, sh[1] + math.cos(ang) * ln)
        cv.capsule(sh, hand, Hh * 0.036, Hh * 0.030, skin, INK, ow)
        mid = (sh[0] + (hand[0] - sh[0]) * 0.42, sh[1] + (hand[1] - sh[1]) * 0.42)
        cv.capsule(sh, mid, Hh * 0.045, Hh * 0.040, shirt, INK, ow)
        cv.ellipse(hand[0], hand[1], Hh * 0.05, Hh * 0.05, skin, INK, ow)
    # ---- boyun + kafa
    cv.capsule((fx, torso_top + 2), (fx, torso_top - head_h * 0.1), Hh * 0.03, Hh * 0.03, skin, INK, ow)
    head_pts_c = (hx, head_cy)
    if species == "hedgehog":
        cv.ellipse(hx - face * head_w * 0.02, head_cy, head_w * 0.52, head_h * 0.50, skin, INK, ow, rot=tilt * 0.3)
        cv.ellipse(hx - head_w * 0.42, head_cy - head_h * 0.38, head_w * 0.12, head_h * 0.12, skin, INK, ow)
        cv.ellipse(hx + head_w * 0.42, head_cy - head_h * 0.38, head_w * 0.12, head_h * 0.12, skin, INK, ow)
    else:
        for sg in (-1, 1):   # kulaklar
            cv.ellipse(hx + sg * head_w * 0.50, head_cy + head_h * 0.04, head_w * 0.09, head_h * 0.12, skin, INK, ow)
        cv.ellipse(hx, head_cy, head_w * 0.52, head_h * 0.52, skin, INK, ow, rot=tilt * 0.3)
    # ---- yüz
    emo = st.get("emotion", "neutral")
    eye_y = head_cy - head_h * 0.04
    ex = head_w * 0.205
    erx, ery = head_w * 0.135, head_h * 0.185
    if emo == "surprise":
        erx *= 1.12; ery *= 1.2
    for sg in (-1, 1):
        cx = hx + sg * ex + face * head_w * 0.12
        far = (sg * face) < -0.2
        rx = erx * (0.82 if far else 1.0)
        if st.get("blink") or emo == "laugh":
            cv.line(cv.arc_pts(cx, eye_y + ery * 0.1, rx, ery * 0.6, math.pi * 1.1, math.pi * 1.9), INK, ow * 1.1) if emo == "laugh" else \
                cv.line([(cx - rx, eye_y + ery * 0.15), (cx + rx, eye_y + ery * 0.15)], INK, ow * 1.2)
        else:
            cv.ellipse(cx, eye_y, rx, ery, (255, 255, 255), INK, ow * 0.9)
            gx = cx + face * rx * 0.38 + st.get("gaze", 0) * rx * 0.25
            pr = rx * 0.62
            cv.ellipse(gx, eye_y + ery * 0.08, pr, pr * 1.25, des["iris"], None, 0)
            cv.ellipse(gx, eye_y + ery * 0.08, pr * 0.58, pr * 0.75, (15, 10, 15), None, 0)
            cv.ellipse(gx - pr * 0.28, eye_y - ery * 0.18, pr * 0.24, pr * 0.24, (255, 255, 255), None, 0)
            cv.line([(cx - rx * 1.05, eye_y - ery * 0.9), (cx + rx * 1.05, eye_y - ery * 0.9)], skin, 0.1)
        # kaş
        by_ = eye_y - ery * 1.45
        slope = {"angry": -0.45, "sad": 0.45, "surprise": 0.0, "laugh": -0.1}.get(emo, 0.08)
        lift = (-ery * 0.35 if emo == "surprise" else 0) - ery * 0.5 * st.get("brow", 0)
        cv.line([(cx - rx * 0.9, by_ + lift + slope * sg * rx * -1 * 0.5), (cx + rx * 0.9, by_ + lift + slope * sg * rx * 0.5)], shade(hair, 0.85) if species != "hedgehog" else hair, ow * 1.4)
    # yanak
    for sg in (-1, 1):
        cv.ellipse(hx + sg * head_w * 0.33 + face * head_w * 0.1, head_cy + head_h * 0.20, head_w * 0.07, head_h * 0.045, (255, 150, 150), None, 0)
    # burun
    if species == "hedgehog":
        cv.ellipse(hx + face * head_w * 0.17, head_cy + head_h * 0.10, head_w * 0.075, head_h * 0.06, (40, 30, 30), None, 0)
    else:
        cv.line(cv.arc_pts(hx + face * head_w * 0.14, head_cy + head_h * 0.08, head_w * 0.035, head_h * 0.04, 0.3, math.pi - 0.3), shade(skin, 0.62), 2.6)
    # ağız
    mouth_letter = st.get("mouth", "X")
    if emo == "laugh" and mouth_letter == "X":
        mouth_letter = "D"
    draw_mouth(cv, hx + face * head_w * 0.14, head_cy + head_h * 0.26, head_w * 0.26, head_h * 0.16, mouth_letter)
    # ---- saç (ön)
    top = head_cy - head_h * 0.50
    if style in ("short", "bob", "ponytail", "bun") and species != "hedgehog":
        pts = cv.arc_pts(hx, head_cy, head_w * 0.545, head_h * 0.54, math.pi * 1.0, math.pi * 2.0, 24)
        fr = [(hx + head_w * 0.54, head_cy - head_h * 0.18), (hx + head_w * 0.36, head_cy - head_h * 0.34), (hx + head_w * 0.16, head_cy - head_h * 0.27),
              (hx - head_w * 0.04, head_cy - head_h * 0.38), (hx - head_w * 0.26, head_cy - head_h * 0.28), (hx - head_w * 0.54, head_cy - head_h * 0.18)]
        cv.poly(pts + fr, hair, INK, ow)
        if style == "bun":
            cv.ellipse(hx, top - head_h * 0.06, head_w * 0.17, head_w * 0.15, hair, INK, ow)
    if style == "spiky" and species != "hedgehog":
        for i in range(7):
            a = math.radians(205 + i * 21.6)
            b = (hx + math.cos(a) * head_w * 0.45, head_cy + math.sin(a) * head_h * 0.50)
            tip = (hx + math.cos(a) * head_w * 0.66, head_cy + math.sin(a) * head_h * 0.72)
            perp = head_w * 0.09
            cv.poly([(b[0] - perp, b[1]), tip, (b[0] + perp, b[1])], hair, INK, ow * 0.8)
        cv.poly(cv.arc_pts(hx, head_cy, head_w * 0.5, head_h * 0.5, math.pi * 1.08, math.pi * 1.92, 16), hair, INK, ow * 0.8)
    if species == "hedgehog":      # alın tutamı
        for k, dx in enumerate((-0.14, 0.0, 0.14)):
            cv.poly([(hx + (dx - 0.07) * head_w, head_cy - head_h * 0.40), (hx + dx * head_w + face * head_w * 0.05, head_cy - head_h * (0.62 + 0.05 * (k % 2))),
                     (hx + (dx + 0.07) * head_w, head_cy - head_h * 0.40)], hair, INK, ow * 0.8)
    # ---- aksesuar
    acc = des["accessory"]
    if acc == "glasses":
        for sg in (-1, 1):
            cv.ellipse(hx + sg * ex + face * head_w * 0.12, eye_y, erx * 1.45, ery * 1.25, (255, 255, 255), None, 0) if False else None
            cv.line(cv.arc_pts(hx + sg * ex + face * head_w * 0.12, eye_y, erx * 1.45, ery * 1.2, 0, 2 * math.pi, 28), INK, ow)
        cv.line([(hx - ex + erx * 1.45 + face * head_w * 0.12, eye_y), (hx + ex - erx * 1.45 + face * head_w * 0.12, eye_y)], INK, ow)
    if acc == "hat":
        cv.ellipse(hx, top + head_h * 0.06, head_w * 0.62, head_h * 0.10, shade(des["accent"], 0.85), INK, ow)
        cv.poly(cv.arc_pts(hx, top + head_h * 0.06, head_w * 0.42, head_h * 0.42, math.pi, 2 * math.pi, 20), des["accent"], INK, ow)
    if acc == "bow":
        cv.ellipse(hx - head_w * 0.38, top + head_h * 0.1, head_w * 0.12, head_w * 0.08, des["accent"], INK, ow)
        cv.ellipse(hx - head_w * 0.22, top + head_h * 0.1, head_w * 0.12, head_w * 0.08, des["accent"], INK, ow)
