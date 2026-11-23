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

    def ellipse_cel(self, cx, cy, rx, ry, fill, ol=INK, ow=3.0, rot=0.0, k=0.80, n=44):
        """Cel gölge: koyu zemin + ışık yönüne (sol-üst) kayık, küçültülmüş açık ton => alt-sağda tek gölge ayı."""
        self.ellipse(cx, cy, rx, ry, shade(fill, k), ol, ow, rot, n)
        self.ellipse(cx - rx * 0.10, cy - ry * 0.11, rx * 0.89, ry * 0.88, fill, None, 0, rot, n)

    def poly_cel(self, pts, fill, ol=INK, ow=3.0, k=0.80):
        cx = sum(p[0] for p in pts) / len(pts); cy = sum(p[1] for p in pts) / len(pts)
        w = max(p[0] for p in pts) - min(p[0] for p in pts); h = max(p[1] for p in pts) - min(p[1] for p in pts)
        self.poly(pts, shade(fill, k), ol, ow)
        self.poly([(cx + (x - cx) * 0.90 - w * 0.035, cy + (y - cy) * 0.90 - h * 0.035) for x, y in pts], fill, None, 0)

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
            "iris": (rgb(spec["eye_color"]) if "eye_color" in spec else iris), "female": female, "age": age, "scarf": col("scarf", accent),
            "build": float(spec.get("build", 1.0)), "face_w": float(spec.get("face_w", 1.0)), "eye_scale": float(spec.get("eye_scale", 1.0)),
            "freckles": int(spec.get("freckles", 0)), "beard": spec.get("beard", "none"), "lashes": bool(spec.get("lashes", False)),
            "earrings": bool(spec.get("earrings", False)), "pregnant": bool(spec.get("pregnant", False)),
            "lowerwear": spec.get("lowerwear") or ("shorts" if cls in ("infant", "toddler", "child") else "pants"),
            "lower_color": col("lower", shorts), "dimple": bool(spec.get("dimple", False)), "brow_w": float(spec.get("brow_w", 1.0)),
            "eye_shape": spec.get("eye_shape", "round"), "eye_dist": float(spec.get("eye_dist", 1.0)), "brow_shape": spec.get("brow_shape", "flat"),
            "nose": spec.get("nose", "line"), "mouth_w": float(spec.get("mouth_w", 1.0)), "blush": float(spec.get("blush", 1.0)),
            "eyebags": bool(spec.get("eyebags", False)), "lid": float(spec.get("lid", 0.0))}


# ---------------------------------------------------------------- ağız şekilleri (Rhubarb A-H, X)
def draw_mouth(cv, mx, my, mw, mh, letter, ol=INK, emo="neutral"):
    dark, tongue = (110, 30, 45), (235, 110, 120)
    L = letter if letter in "ABCDEFGHX" else "X"
    if L == "X":
        if emo == "sad":        # somurtma: ağız aşağı kıvrık
            cv.line(cv.arc_pts(mx, my + mh * 0.55, mw * 0.4, mh * 0.45, math.pi + 0.3, 2 * math.pi - 0.3), ol, 3.2); return
        if emo == "angry":      # sıkılı dudak
            cv.line([(mx - mw * 0.4, my + mh * 0.1), (mx + mw * 0.4, my + mh * 0.1)], ol, 4.0); return
        if emo == "sly":        # yan sırıtma
            cv.line([(mx - mw * 0.35, my + mh * 0.12), (mx + mw * 0.05, my + mh * 0.2), (mx + mw * 0.45, my - mh * 0.1)], ol, 3.4); return
        k = 0.8 if emo in ("happy", "laugh") else 0.55
        cv.line(cv.arc_pts(mx, my - mh * 0.4, mw * (0.62 if emo in ("happy", "laugh") else 0.5), mh * k, 0.2, math.pi - 0.2), ol, 3.2); return
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


# ---------------------------------------------------------------- eller
def _hand(cv, pos, r, skin, sg, fwd, ow, t, emo, g=None):
    """Beş parmaklı el: avuç + başparmak + 4 parmak. Açıklık eylemle (fwd) ve duyguyla değişir: kapalı yumruk <-> açık avuç."""
    openness = max(0.0, min(1.0, 0.55 + 0.35 * math.sin(abs(fwd) * 2.0 + t * 1.3) + (0.3 if emo in ("surprise", "laugh", "happy") else 0)))
    x, y = pos
    if g in ("point", "thumb", "fist"):                  # jest elleri: işaret (tek parmak), başparmak yukarı, yumruk
        cv.ellipse(x, y, r * 0.95, r * 0.9, skin, INK, ow * 0.9)
        if g == "point":
            cv.capsule((x, y - r * 0.3), (x - sg * r * 0.2, y - r * 1.9), r * 0.22, r * 0.18, skin, INK, ow * 0.7)
            for i in range(3):
                cv.ellipse(x + (i - 1) * r * 0.45, y + r * 0.2, r * 0.26, r * 0.3, skin, INK, ow * 0.6)
        elif g == "thumb":
            cv.capsule((x - sg * r * 0.2, y - r * 0.3), (x - sg * r * 0.25, y - r * 1.7), r * 0.3, r * 0.26, skin, INK, ow * 0.8)
            for i in range(4):
                cv.ellipse(x + (i - 1.5) * r * 0.38, y + r * 0.25, r * 0.22, r * 0.28, skin, INK, ow * 0.55)
        else:
            for i in range(4):
                cv.ellipse(x + (i - 1.5) * r * 0.4, y - r * 0.05, r * 0.24, r * 0.3, skin, INK, ow * 0.55)
        return
    cv.ellipse(x, y, r * 0.95, r * 0.9, skin, INK, ow * 0.9)
    cv.capsule((x - sg * r * 0.55, y - r * 0.05), (x - sg * r * 1.05, y - r * (0.25 + 0.5 * openness)), r * 0.28, r * 0.22, skin, INK, ow * 0.8)
    for i in range(4):
        a = math.radians(-100 + i * 24) if sg > 0 else math.radians(-80 - i * 24)
        L = r * (0.55 + 0.65 * openness) * (1.0 - 0.1 * abs(i - 1.5))
        base = (x + math.cos(a) * r * 0.72, y + math.sin(a) * r * 0.62)
        tip = (x + math.cos(a) * (r * 0.72 + L), y + math.sin(a) * (r * 0.62 + L * (0.75 if openness > 0.4 else 0.35)) + (r * 0.25 if openness < 0.35 else 0))
        cv.capsule(base, tip, r * 0.20, r * 0.17, skin, INK, ow * 0.7)
    cv.ellipse(x - sg * r * 0.05, y + r * 0.08, r * 0.78, r * 0.7, skin, None, 0)


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
    torso_w *= des.get("build", 1.0)
    ow = max(3.0, Hh * 0.019)
    jump = pose["z"] * ppm
    sit = max(0.0, -pose["z"]) * ppm
    by = fy - jump                       # gövde tabanı (ayak) y
    squash = 1.0 + max(0.0, jump) / (Hh * 3.0) + 0.014 * math.sin(t * 2.4 + des["age"])
    sq_ = float(pose.get("sq", 1.0))
    squash *= sq_
    torso_w /= max(0.7, sq_) ** 0.5            # hacim korunur: ezilince genişler, uzayınca incelir
    pulse = float(st.get("pulse", 0.0))   # vurgu/şaşkınlıkta ezilip esneme (squash & stretch)
    if st.get("emotion") in ("surprise", "laugh"):
        pulse = max(pulse, 0.6 + 0.3 * math.sin(t * 9))
    if pulse:
        squash *= 1.0 - 0.10 * pulse
        head_h *= 1.0 + 0.12 * pulse
        head_w = head_h * 1.12
    head_w *= des.get("face_w", 1.0)
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
    if style == "wavy_long":      # uzun dalgalı saç: omuza dökülür, ucu dalgalı
        wv = math.sin(t * 1.7 + des["age"]) * head_w * 0.02
        pts = [(hx - head_w * 0.58, head_cy - head_h * 0.1), (hx - head_w * 0.66 + wv, head_cy + head_h * 0.45), (hx - head_w * 0.50 - wv, head_cy + head_h * 0.95),
               (hx - head_w * 0.28 + wv, head_cy + head_h * 0.82), (hx, head_cy + head_h * 1.0), (hx + head_w * 0.28 - wv, head_cy + head_h * 0.82),
               (hx + head_w * 0.50 + wv, head_cy + head_h * 0.95), (hx + head_w * 0.66 - wv, head_cy + head_h * 0.45), (hx + head_w * 0.58, head_cy - head_h * 0.1)]
        cv.poly(pts, hair, INK, ow)
    if style == "curly":          # kıvırcık: saç çevresinde yumak halkası
        for i in range(11):
            a = math.radians(160 + i * 22)
            cv.ellipse(hx + math.cos(a) * head_w * 0.52, head_cy + math.sin(a) * head_h * 0.50 + head_h * 0.06, head_w * 0.17, head_w * 0.17, hair, INK, ow * 0.9)
        if des.get("class") == "adult":      # uzun kıvırcık: omuz hizası yumaklar
            for sg in (-1, 1):
                for k in range(3):
                    cv.ellipse(hx + sg * head_w * (0.56 + 0.04 * (k % 2)), head_cy + head_h * (0.28 + 0.2 * k), head_w * 0.15, head_w * 0.15, hair, INK, ow * 0.9)
    if style == "hijab":      # başörtüsü: arka katman + omuza dökülen kumaş
        sc_ = des["scarf"]
        cv.ellipse(hx, head_cy + head_h * 0.50, head_w * 0.66, head_h * 0.34, shade(sc_, 0.88), INK, ow)
        cv.ellipse(hx, head_cy + head_h * 0.06, head_w * 0.64, head_h * 0.66, sc_, INK, ow)

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
        lw = des.get("lowerwear", "shorts"); lc = des.get("lower_color", shorts)
        if lw == "pants":      # yetişkin: bacak tamamen pantolon
            cv.capsule(top, (foot[0], foot[1] - Hh * 0.025), Hh * 0.058, Hh * 0.047, lc, INK, ow)
        elif lw == "skirt":    # uzun etek/elbise: bacak görünmez, yalnız ayak ucu
            pass
        else:
            cv.capsule(top, (foot[0], foot[1] - Hh * 0.03), Hh * 0.045, Hh * 0.04, skin if species != "hedgehog" else skin, INK, ow)
            cv.capsule(top, ((top[0] + foot[0]) / 2, (top[1] + foot[1]) / 2 - Hh * 0.01), Hh * 0.055, Hh * 0.05, shorts, INK, ow)
        cv.ellipse(foot[0] + sg * Hh * 0.025, foot[1], Hh * 0.075, Hh * 0.04, shade(des["accent"], 0.9), INK, ow)
    # ---- gövde
    tpts = [(fx - torso_w * 0.5, torso_top + torso_h * 0.10), (fx - torso_w * 0.36, torso_top), (fx + torso_w * 0.36, torso_top),
            (fx + torso_w * 0.5, torso_top + torso_h * 0.10), (fx + torso_w * 0.55, torso_bot), (fx - torso_w * 0.55, torso_bot)]
    cv.poly_cel(tpts, shirt, INK, ow)
    if des.get("lowerwear") == "skirt":
        sk_top = torso_bot - torso_h * 0.10; ank = by - Hh * 0.05
        cv.poly([(fx - torso_w * 0.55, sk_top), (fx + torso_w * 0.55, sk_top), (fx + torso_w * 0.95, ank), (fx - torso_w * 0.95, ank)], shirt, INK, ow)
    if des.get("pregnant"):
        cv.ellipse(fx + torso_w * 0.12, torso_top + torso_h * 0.70, torso_w * 0.46, torso_h * 0.36, shade(shirt, 1.04), INK, ow)
    cv.ellipse(fx, torso_top + torso_h * 0.52, torso_w * 0.13, torso_w * 0.13, des["accent"], INK, ow * 0.7)
    if des.get("lowerwear") != "skirt":
        cv.poly([(fx - torso_w * 0.55, torso_bot - torso_h * 0.14), (fx + torso_w * 0.55, torso_bot - torso_h * 0.14),
                 (fx + torso_w * 0.55, torso_bot), (fx - torso_w * 0.55, torso_bot)], des.get("lower_color", shorts), None, 0)
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
        _hand(cv, hand, Hh * 0.052, skin, sg, fwd, ow, t, st.get("emotion", "neutral"), pose.get("hand") if pose.get("hand_side") == side else None)
    # ---- boyun + kafa
    cv.capsule((fx, torso_top + 2), (fx, torso_top - head_h * 0.1), Hh * 0.03, Hh * 0.03, skin, INK, ow)
    head_pts_c = (hx, head_cy)
    if species == "hedgehog":
        cv.ellipse(hx - face * head_w * 0.02, head_cy, head_w * 0.52, head_h * 0.50, skin, INK, ow, rot=tilt * 0.3)
        cv.ellipse(hx - head_w * 0.42, head_cy - head_h * 0.38, head_w * 0.12, head_h * 0.12, skin, INK, ow)
        cv.ellipse(hx + head_w * 0.42, head_cy - head_h * 0.38, head_w * 0.12, head_h * 0.12, skin, INK, ow)
    else:
        for sg in (-1, 1):   # kulaklar (dönüşte uzak kulak kafanın arkasında kalır)
            if sg * face < -0.55:
                continue
            cv.ellipse(hx + sg * head_w * 0.50 * (1 - 0.25 * abs(face)), head_cy + head_h * 0.04, head_w * 0.09, head_h * 0.12, skin, INK, ow)
        cv.ellipse_cel(hx - face * head_w * 0.03, head_cy, head_w * 0.52 * (1.0 - 0.07 * abs(face)), head_h * 0.52, skin, INK, ow, rot=tilt * 0.3, k=0.86)
    # ---- yüz
    emo = st.get("emotion", "neutral")
    eye_y = head_cy - head_h * 0.04
    ex = head_w * 0.205
    es_ = des.get("eye_scale", 1.0) * (0.84 if des.get("class") == "adult" else 1.0)     # yetişkinde göz yüze göre daha küçük
    erx, ery = head_w * 0.135 * es_, head_h * 0.185 * es_
    shp = des.get("eye_shape", "round")
    erx *= {"round": 1.0, "almond": 1.12, "wide": 1.08, "narrow": 0.92, "sleepy": 1.05}.get(shp, 1.0)
    ery *= {"round": 1.0, "almond": 0.74, "wide": 1.12, "narrow": 0.80, "sleepy": 0.80}.get(shp, 1.0)
    ex = ex * des.get("eye_dist", 1.0)
    if emo == "surprise":
        erx *= 1.12; ery *= 1.2
    for sg in (-1, 1):
        cx = hx + sg * ex * (1.0 - 0.16 * abs(face)) + face * head_w * 0.19
        far = (sg * face) < -0.2
        rx = erx * (0.82 if far else 1.0)
        if st.get("blink") or emo == "laugh":
            cv.line(cv.arc_pts(cx, eye_y + ery * 0.1, rx, ery * 0.6, math.pi * 1.1, math.pi * 1.9), INK, ow * 1.1) if emo == "laugh" else \
                cv.line([(cx - rx, eye_y + ery * 0.15), (cx + rx, eye_y + ery * 0.15)], INK, ow * 1.2)
        else:
            cv.ellipse(cx, eye_y, rx, ery, (255, 255, 255), INK, ow * 0.45)
            gx = cx + face * rx * 0.38 + st.get("gaze", 0) * rx * 0.25
            pr = rx * (0.46 if emo in ("surprise", "scared") else 0.62)           # korku/şaşkınlık: göz bebeği küçülür, beyaz görünür
            cv.ellipse(gx, eye_y + ery * 0.08, pr, pr * 1.25, des["iris"], None, 0)
            cv.ellipse(gx, eye_y + ery * 0.08, pr * 0.58, pr * 0.75, (15, 10, 15), None, 0)
            cv.ellipse(gx - pr * 0.28, eye_y - ery * 0.18, pr * 0.24, pr * 0.24, (255, 255, 255), None, 0)
            if emo in ("happy", "laugh"):                   # mutlu: alt göz kapağı yukarı kalkar (gülen göz)
                cv.poly([(cx - rx * 1.05, eye_y + ery * 1.1), (cx + rx * 1.05, eye_y + ery * 1.1), (cx + rx * 0.95, eye_y + ery * 0.42), (cx - rx * 0.95, eye_y + ery * 0.42)], skin, None, 0)
            lidk = {"angry": 0.34, "sly": 0.42, "sad": 0.22, "sleepy": 0.5, "laugh": 0.0}.get(emo, des.get("lid", 0.0) and 0.0)
            if lidk:
                yl = eye_y - ery + 2 * ery * lidk
                cv.poly([(cx - rx * 1.06, eye_y - ery * 1.1), (cx + rx * 1.06, eye_y - ery * 1.1), (cx + rx * 1.0, yl + (-sg * ery * 0.12 if emo == "angry" else 0)), (cx - rx * 1.0, yl + (sg * ery * 0.12 if emo == "angry" else 0))], skin, None, 0)
            cv.line(cv.arc_pts(cx, eye_y + ery * 0.05, rx * 1.04, ery * 1.04, math.pi * 1.06, math.pi * 1.94, 14), INK, ow * 0.95)
            if des.get("lid", 0) > 0:      # düşük üst göz kapağı: yorgun/uykulu bakış
                y_l = eye_y - ery + 2 * ery * des["lid"]
                cv.poly([(cx - rx * 1.04, eye_y - ery * 1.08), (cx + rx * 1.04, eye_y - ery * 1.08), (cx + rx * 0.95, y_l), (cx - rx * 0.95, y_l)], skin, None, 0)
                cv.line([(cx - rx * 0.97, y_l), (cx + rx * 0.97, y_l)], INK, ow * 0.9)
        if des.get("eyebags"):
            cv.line(cv.arc_pts(cx, eye_y + ery * 1.30, rx * 0.95, ery * 0.5, math.pi * 0.15, math.pi * 0.85), shade(skin, 0.74), 2.4)
        if des.get("lashes"):
            for k_ in (-1, 0, 1):
                lx = cx + sg * rx * (0.55 + 0.25 * k_ * 0.8)
                cv.line([(lx, eye_y - ery * 0.85), (lx + sg * rx * 0.28, eye_y - ery * 1.28)], INK, ow * 0.8)
        # kaş
        by_ = eye_y - ery * 1.45
        slope = {"angry": -0.65, "sly": -0.25, "sad": 0.55, "surprise": 0.0, "laugh": -0.1}.get(emo, 0.08)
        lift = (-ery * 0.35 if emo == "surprise" else (-ery * 0.28 if emo in ("curious", "happy") else 0)) - ery * 0.5 * st.get("brow", 0)
        if emo == "curious" and sg > 0:
            lift -= ery * 0.25          # tek kaş daha yukarıda (merak)
        p0 = (cx - rx * 0.9, by_ + lift + slope * sg * rx * -1 * 0.5); p1 = (cx + rx * 0.9, by_ + lift + slope * sg * rx * 0.5)
        bw_ = ow * 1.7 * des.get("brow_w", 1.0); bs_ = des.get("brow_shape", "flat")
        if bs_ == "arched":
            pts_ = [p0, ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2 - ery * 0.30), p1]
        elif bs_ == "soft":
            pts_ = [p0, ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2 - ery * 0.14), p1]
        elif bs_ == "thick":
            pts_ = [(p0[0], p0[1] + ery * 0.12), p1]; bw_ *= 1.7
        else:
            pts_ = [p0, p1]
        cv.line(pts_, shade(hair, 0.85) if species != "hedgehog" else hair, bw_)
    # yanak
    for sg in (-1, 1):
        bl_ = des.get("blush", 1.0); cc_ = tuple(int(skin[i_] + ((255, 150, 150)[i_] - skin[i_]) * bl_) for i_ in range(3))
        cv.ellipse(hx + sg * head_w * 0.33 + face * head_w * 0.1, head_cy + head_h * 0.20, head_w * 0.07, head_h * 0.045, cc_, None, 0)
    for k_ in range(des.get("freckles", 0)):       # çiller: sol yanak (izleyiciye göre sağ)
        cv.ellipse(hx - head_w * (0.30 - 0.05 * k_) + face * head_w * 0.1, head_cy + head_h * (0.12 + 0.025 * (k_ % 2)) + head_h * 0.02, head_w * 0.018, head_w * 0.018, shade(skin, 0.68), None, 0)
    if des.get("earrings"):
        for sg in (-1, 1):
            cv.ellipse(hx + sg * head_w * 0.50, head_cy + head_h * 0.20, head_w * 0.035, head_w * 0.035, (240, 200, 80), INK, ow * 0.5)
    bd = des.get("beard", "none")
    if bd in ("short", "full", "stubble"):      # sakal: çene hattı boyunca (stubble = kirli sakal, çizgisiz)
        depth = head_h * (0.20 if bd in ("short", "stubble") else 0.34)
        jaw = cv.arc_pts(hx, head_cy + head_h * 0.02, head_w * 0.50, head_h * 0.50, math.pi * 0.08, math.pi * 0.92, 20)
        inner = [(x, y - depth * (0.35 + 0.65 * abs(math.sin((x - hx) / (head_w * 0.5 + 1e-6) * 1.2)) )) for x, y in reversed(jaw)]
        bcol = tuple(int(skin[i_] * 0.62 + hair[i_] * 0.38) for i_ in range(3)) if bd == "stubble" else shade(hair, 0.9)
        cv.poly(jaw + inner, bcol, INK if bd == "full" else None, ow * 0.8)
    # burun
    if species == "hedgehog":
        cv.ellipse(hx + face * head_w * 0.17, head_cy + head_h * 0.10, head_w * 0.075, head_h * 0.06, (40, 30, 30), None, 0)
    else:
        nx_, ny_ = hx + face * head_w * 0.22, head_cy + head_h * 0.08; nt_ = des.get("nose", "line")
        if nt_ == "dot":
            cv.ellipse(nx_, ny_ + head_h * 0.02, head_w * 0.022, head_h * 0.022, shade(skin, 0.72), None, 0)
        elif nt_ == "button":
            cv.ellipse(nx_, ny_ + head_h * 0.015, head_w * 0.04, head_h * 0.035, shade(skin, 0.95), shade(skin, 0.64), 1.6)
        elif nt_ == "round":
            cv.ellipse(nx_, ny_ + head_h * 0.02, head_w * 0.062, head_h * 0.05, shade(skin, 0.94), shade(skin, 0.6), 2.0)
        elif nt_ == "long":
            cv.line([(nx_ - face * head_w * 0.01, ny_ - head_h * 0.12), (nx_, ny_ + head_h * 0.02)], shade(skin, 0.66), 2.2)
            cv.line(cv.arc_pts(nx_, ny_ + head_h * 0.03, head_w * 0.05, head_h * 0.035, 0.2, math.pi - 0.2), shade(skin, 0.62), 2.6)
        else:
            cv.line(cv.arc_pts(nx_, ny_, head_w * 0.035, head_h * 0.04, 0.3, math.pi - 0.3), shade(skin, 0.62), 2.6)
    # ağız
    mouth_letter = st.get("mouth", "X")
    if emo == "laugh" and mouth_letter == "X":
        mouth_letter = "D"
    draw_mouth(cv, hx + face * head_w * 0.20, head_cy + head_h * 0.26, head_w * 0.26 * des.get("mouth_w", 1.0), head_h * 0.16, mouth_letter, INK, emo)
    if des.get("dimple"):
        cv.line(cv.arc_pts(hx + face * head_w * 0.14 + head_w * 0.17, head_cy + head_h * 0.27, head_w * 0.03, head_h * 0.03, -1.2, 1.2), shade(skin, 0.6), 2.4)
    # ---- saç (ön)
    top = head_cy - head_h * 0.50
    if style in ("short", "bob", "ponytail", "bun", "wavy_long", "curly", "bangs") and species != "hedgehog":
        pts = cv.arc_pts(hx, head_cy, head_w * 0.545, head_h * 0.54, math.pi * 1.0, math.pi * 2.0, 24)
        fr = [(hx + head_w * 0.54, head_cy - head_h * 0.18), (hx + head_w * 0.36, head_cy - head_h * 0.34), (hx + head_w * 0.16, head_cy - head_h * 0.27),
              (hx - head_w * 0.04, head_cy - head_h * 0.38), (hx - head_w * 0.26, head_cy - head_h * 0.28), (hx - head_w * 0.54, head_cy - head_h * 0.18)]
        cv.poly(pts + fr, hair, INK, ow)
        if style == "bun":
            cv.ellipse(hx, top - head_h * 0.06, head_w * 0.17, head_w * 0.15, hair, INK, ow)
    if style in ("bob", "bangs") and des.get("class") in ("toddler", "child") and des["female"]:   # küt kâhkül
        cv.poly([(hx - head_w * 0.52, head_cy - head_h * 0.20), (hx - head_w * 0.30, head_cy - head_h * 0.08), (hx + head_w * 0.30, head_cy - head_h * 0.08),
                 (hx + head_w * 0.52, head_cy - head_h * 0.20), (hx + head_w * 0.40, head_cy - head_h * 0.45), (hx - head_w * 0.40, head_cy - head_h * 0.45)], hair, INK, ow * 0.8)
    if des.get("hat_kind") == "beanie":
        pass
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
    if style == "hijab":      # yüzü çerçeveleyen ön şerit
        sc_ = des["scarf"]
        outer = cv.arc_pts(hx, head_cy - head_h * 0.02, head_w * 0.60, head_h * 0.58, math.pi * 1.04, math.pi * 1.96, 26)
        inner = cv.arc_pts(hx, head_cy + head_h * 0.02, head_w * 0.46, head_h * 0.44, math.pi * 1.96, math.pi * 1.04, 26)
        cv.poly(outer + inner, sc_, INK, ow * 0.9)
    if acc == "flower_pin":   # sarı çiçek iğnesi (başörtüsünde)
        fx_, fy_, fr_ = hx + head_w * 0.46, head_cy + head_h * 0.34, head_w * 0.075
        for k_ in range(5):
            a_ = k_ * 2 * math.pi / 5
            cv.ellipse(fx_ + math.cos(a_) * fr_ * 0.8, fy_ + math.sin(a_) * fr_ * 0.8, fr_ * 0.55, fr_ * 0.55, (255, 214, 60), INK, ow * 0.5)
        cv.ellipse(fx_, fy_, fr_ * 0.45, fr_ * 0.45, (230, 120, 40), INK, ow * 0.4)
    if acc == "star":         # sarı yıldız toka
        cx_, cy_, r_ = hx - head_w * 0.30, top + head_h * 0.16, head_w * 0.12
        pts = []
        for i in range(10):
            a = -math.pi / 2 + i * math.pi / 5; rr = r_ if i % 2 == 0 else r_ * 0.45
            pts.append((cx_ + math.cos(a) * rr, cy_ + math.sin(a) * rr))
        cv.poly(pts, (255, 214, 60), INK, ow * 0.7)
    if acc == "glasses":
        for sg in (-1, 1):
            cv.ellipse(hx + sg * ex + face * head_w * 0.12, eye_y, erx * 1.45, ery * 1.25, (255, 255, 255), None, 0) if False else None
            cv.line(cv.arc_pts(hx + sg * ex + face * head_w * 0.12, eye_y, erx * 1.45, ery * 1.2, 0, 2 * math.pi, 28), INK, ow)
        cv.line([(hx - ex + erx * 1.45 + face * head_w * 0.12, eye_y), (hx + ex - erx * 1.45 + face * head_w * 0.12, eye_y)], INK, ow)
    if acc == "hat":
        cv.ellipse(hx, top + head_h * 0.06, head_w * 0.62, head_h * 0.10, shade(des["accent"], 0.85), INK, ow)
        cv.poly(cv.arc_pts(hx, top + head_h * 0.06, head_w * 0.42, head_h * 0.42, math.pi, 2 * math.pi, 20), des["accent"], INK, ow)
    if acc == "beanie":       # ayıcık kulaklı bere
        bc = des["accent"]
        for sg in (-1, 1):
            cv.ellipse(hx + sg * head_w * 0.36, top + head_h * 0.02, head_w * 0.11, head_w * 0.11, bc, INK, ow)
            cv.ellipse(hx + sg * head_w * 0.36, top + head_h * 0.03, head_w * 0.05, head_w * 0.05, shade(bc, 0.8), None, 0)
        cv.poly(cv.arc_pts(hx, head_cy - head_h * 0.02, head_w * 0.56, head_h * 0.56, math.pi * 1.0, math.pi * 2.0, 24), bc, INK, ow)
    if acc == "bow":
        cv.ellipse(hx - head_w * 0.38, top + head_h * 0.1, head_w * 0.12, head_w * 0.08, des["accent"], INK, ow)
        cv.ellipse(hx - head_w * 0.22, top + head_h * 0.1, head_w * 0.12, head_w * 0.08, des["accent"], INK, ow)
