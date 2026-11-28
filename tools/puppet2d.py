"""AHOS 2D Kesme-Kukla Motoru (diziden bağımsız, saf Python + Pillow).

Vektör karakterler (büyük gözler, ifade, 9 Rhubarb ağız şekli), boyalı arka planlar, kalın kenar çizgisi.
Poz girdisi shot_motion.pose_at çıktısıdır. Her şey 'spec' ve 'sahne türü'nden üretilir; belirli bir diziye bağlı değildir.
"""
import colorsys, hashlib, math, random, sys
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
def designs_for(bible, assets_dir):
    """Tek kaynak: bible + <assets>/<id>.spec.json -> {id: tasarım}. Planlayıcı, render ve testler aynı boy/oranı kullanır."""
    import json as _j, os as _o
    out = {}
    for ch in bible["characters"]:
        sp = _o.path.join(assets_dir, f"{ch['id']}.spec.json")
        out[ch["id"]] = derive_design(ch, _j.load(open(sp, encoding="utf-8")) if _o.path.exists(sp) else {})
    return out


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
def draw_mouth(cv, mx, my, mw, mh, letter, ol=INK, emo="neutral", skin=None):
    dark, tongue = (110, 30, 45), (235, 110, 120)
    if skin is not None:                        # ağız içi tenle aynı parlaklıktaysa koyulaşır (çok koyu tende dudak çizgisi açık renktir)
        dark = next((c for c in (dark, shade(dark, 0.6), shade(dark, 0.3)) if abs(luma(c) - luma(skin)) >= FACE_LINE_LUM - 4), dark)
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
def view_of(pose):
    """Görünüş sınıfı: 'front' | 'three_quarter' | 'side'. Gövde dönüşü = yaw*1.25."""
    if pose.get("view") in ("front", "three_quarter", "side"):
        return pose["view"]                    # hareket motoru açıkça seçtiyse (salınım görünüşü titretmesin)
    b = abs(max(-1.0, min(1.0, pose.get("yaw", 0.0) * 1.25)))
    if b >= 0.95: return "side"
    return "three_quarter" if b >= 0.45 else "front"


def _elbow(sh, hand, arm_len, sg):
    """Omuz ile el arasında dirsek noktası (ekran y aşağı): iki parça (üst kol + ön kol, her biri arm_len/2). El aşağıdayken dirsek gövdeden
    DIŞA, el yana uzanmışken ve yukarıdayken AŞAĞI/DIŞA bükülür. Arada büküm sürekli olarak sıfırdan geçer (dirsek arkaya döner, kısalmış görünür);
    taraf tek karede değişmez ve dirsek gövdenin içine doğru katlanmaz."""
    dx, dy = hand[0] - sh[0], hand[1] - sh[1]; d = math.hypot(dx, dy) or 1e-6
    half = arm_len / 2.0; hgt = math.sqrt(max(0.0, half * half - (d / 2.0) ** 2))
    a = math.atan2(sg * dx, dy)                            # kolun yönü: 0 = aşağı, +pi/2 = dışa yatay
    f = math.cos(2.0 * a) if abs(a) < math.pi / 2 else -1.0
    nx, ny = sg * math.cos(a), -math.sin(a)
    return ((sh[0] + hand[0]) / 2 + nx * hgt * f, (sh[1] + hand[1]) / 2 + ny * hgt * f)


# ---------------------------------------------------------------- çömelme (tek geometri: çizim, el konumu, omuz ve erişim ölçüsü aynı değeri kullanır)
LEG_K = {"infant": 0.20, "toddler": 0.24, "child": 0.28, "adult": 0.38}
CROUCH_MAX_K = 0.75       # kalça en çok bacak boyunun bu kadarı alçalır (ayaklar yerde, diz bükülür)
KNEE_FRONT_K = 0.55
KNEEL_SLACK_K = 0.5       # omuz farkının (kısa olanın kol boyunun bu katı kadar) küçük kısmı çömelmeden kolla kapanır


def crouch_of(des, pose):
    """Pozdaki çömelme miktarı (metre), fiziksel sınıra kırpılmış."""
    return max(0.0, min(float(pose.get("crouch", 0.0)), CROUCH_MAX_K * des["height"] * LEG_K[des["class"]]))


def _standing(x):
    return {"x": x, "z": 0.0, "yaw": 0.0, "lean": 0.0, "sq": 1.0}


def kneel_drops(des_a, des_b):
    """El değiştirmede kim ne kadar çömelmeli: (a_metre, b_metre). Yalnız omzu yüksek olan çömelir; benzer boylarda 0 (eşik sıçraması yok, sürekli)."""
    ha = shoulder_offset(des_a, _standing(0.0), "R")[1]; hb = shoulder_offset(des_b, _standing(0.0), "R")[1]
    slack = KNEEL_SLACK_K * 0.27 * min(des_a["height"], des_b["height"])
    need = max(0.0, abs(ha - hb) - slack)
    da = crouch_of(des_a, {"crouch": need}) if ha > hb else 0.0
    db = crouch_of(des_b, {"crouch": need}) if hb > ha else 0.0
    return da, db


def _knee(hip, foot, leg_len, outward):
    """Kalça ile ayak arasında diz: iki eşit parça; diz yatayda 'outward' (+1/-1) yönüne bükülür."""
    dx, dy = foot[0] - hip[0], foot[1] - hip[1]; d = math.hypot(dx, dy) or 1e-6
    half = max(leg_len, d) / 2.0; off = math.sqrt(max(0.0, half * half - (d / 2.0) ** 2))
    nx, ny = -dy / d, dx / d
    if nx * outward < 0:
        nx, ny = -nx, -ny
    return (hip[0] + foot[0]) / 2 + nx * off, (hip[1] + foot[1]) / 2 + ny * off


def shoulder_offset(des, pose, side):
    """Omzun ayağa göre konumu (metre): (dx, yükseklik). hand_offset ile aynı geometri."""
    if view_of(pose) == "side":
        Hh = des["height"]; cls = des["class"]
        leg_h = Hh * {"infant": 0.20, "toddler": 0.24, "child": 0.28, "adult": 0.38}[cls]
        torso_h = Hh * {"infant": 0.22, "toddler": 0.25, "child": 0.27, "adult": 0.30}[cls]
        top = -pose["z"] - leg_h - max(0.0, -pose["z"]) - torso_h * float(pose.get("sq", 1.0)) + crouch_of(des, pose)
        d = 1.0 if pose.get("yaw", 0.0) >= 0 else -1.0
        return pose.get("lean", 0.0) * torso_h * 0.5 * d * 0.8, -(top + torso_h * 0.16)
    Hh = des["height"]; cls = des["class"]
    leg_h = Hh * {"infant": 0.20, "toddler": 0.24, "child": 0.28, "adult": 0.38}[cls]
    torso_h = Hh * {"infant": 0.22, "toddler": 0.25, "child": 0.27, "adult": 0.30}[cls]
    torso_w = Hh * {"infant": 0.30, "toddler": 0.28, "child": 0.25, "adult": 0.22}[cls] * des.get("build", 1.0)
    sq_ = float(pose.get("sq", 1.0)); jump = pose["z"]; sit = max(0.0, -pose["z"])
    squash = (1.0 + max(0.0, jump) / (Hh * 3.0)) * sq_
    torso_w /= max(0.7, sq_) ** 0.5
    bturn = max(-1.0, min(1.0, pose.get("yaw", 0.0) * 1.25)); torso_w *= 1.0 - 0.30 * abs(bturn)
    torso_top = -jump - leg_h - sit - torso_h * squash + crouch_of(des, pose)
    sg = -1 if side == "L" else 1
    return sg * torso_w * 0.52, -(torso_top + torso_h * 0.14)


def arm_toward(des, pose, side, tx, th):
    """Yönlü uzanma (hafif IK, ön görünüş): elin hedefe (ayağa göre dx, yükseklik) gitmesi için kol açısını ayarlar (pose'u yerinde değiştirir).
    Dönen: ulaşılabilirlik oranı = (omuz->hedef mesafe) / (kol boyu); ≤1 ise el hedefe ulaşır, >1 ise kısa kalır (kol uzayamaz)."""
    sg = -1 if side == "L" else 1
    shx, shh = shoulder_offset(des, pose, side)
    vx, vdown = tx - shx, -(th - shh)
    ln = des["height"] * 0.27
    ang = max(0.0, min(3.0, math.atan2(sg * vx, vdown)))
    ratio = math.hypot(vx, vdown) / ln
    key = "aL" if side == "L" else "aR"
    pose[key][0] = 0.0; pose[key][1] = ang if side == "L" else -ang
    pose["d" + side] = min(math.hypot(vx, vdown), ln)                                   # el mesafesi: hedefe kadar; yakınsa dirsek bükülür, uzaksa kol tam gerilir
    return ratio


def arm_blend(des, pose, side, tx, th, w):
    """Kolu o anki pozdan (w=0) hedefe uzanmış poza (w=1) sürekli geçirir. Açı ile birlikte EL MESAFESİ de karışır: yalnız açı karışsaydı
    pencere açılıp kapanırken el tek karede bükülü pozdan gergin poza (ya da tersi) sıçrardı."""
    key = "aL" if side == "L" else "aR"; old = list(pose[key]); full = des["height"] * 0.27
    old_len = min(full, pose["d" + side]) if ("d" + side) in pose else full * (1.0 - 0.28 * min(1.0, abs(old[0]) / 1.3))
    had = ("d" + side) in pose
    ratio = arm_toward(des, pose, side, tx, th)
    pose[key] = [old[0] + (pose[key][0] - old[0]) * w, old[1] + (pose[key][1] - old[1]) * w]
    if w <= 0.0 and not had:
        del pose["d" + side]
    else:
        pose["d" + side] = old_len + (pose["d" + side] - old_len) * w
    return ratio


def arm_joints(des, pose, side):
    """Çizilen kolun (omuz, dirsek, el) noktaları, ayağa göre metre: (dx, yükseklik). Ön/üç-çeyrek görünüş; çizimle aynı geometri."""
    full = des["height"] * 0.27
    sx, sh = shoulder_offset(des, pose, side); hx, hh = hand_offset(des, pose, side)
    if ("d" + side) in pose and math.hypot(hx - sx, hh - sh) < full * 0.985:
        ex, ey = _elbow((sx, -sh), (hx, -hh), full, -1 if side == "L" else 1)
        return (sx, sh), (ex, -ey), (hx, hh)
    return (sx, sh), ((sx + hx) / 2, (sh + hh) / 2), (hx, hh)


HAND_R_K = 0.052          # el yarıçapı / boy (draw_grip ile aynı oran)
GRIP_SPLIT_K = 1.0        # iki elin kavrama noktaları arasındaki dikey aralık / (iki el yarıçapının toplamı)


def grip_points(des_a, sh_a, des_b, sh_b, span=None):
    """El değiştirmede iki el AYNI noktaya binmez: nesnenin iki ayrı yerinden kavranır (önde çizilen üst noktadan = buluşma
    çizgisi, arkadaki onun altından: öndekinin yüzü/eli arkadakinin elini örtmesin).
    span: nesnenin kavranabilir dikey uzunluğu (m); aralık bunu aşamaz (küçük nesnede iki el de nesneye değmeli). Dönüş: ((x, h)_a, (x, h)_b)."""
    mx, mh = meeting_point(des_a, sh_a, des_b, sh_b)
    split = GRIP_SPLIT_K * HAND_R_K * (des_a["height"] + des_b["height"])
    if span is not None:
        split = min(split, max(0.0, span))
    a_up = (-des_a["height"], sh_a[0]) > (-des_b["height"], sh_b[0])         # önde çizilen el üstte (derinlik sırası kuralıyla aynı anahtar: kısa önde; eşitse sağdaki)
    up, down = (mx, mh), (mx, mh - split)
    return (up, down) if a_up else (down, up)


def handoff_reach_ratio(des_a, xa, des_b, xb, side_a=None, side_b=None):
    """İki karakter x konumlarında el değiştirebilir mi? Buluşma noktası (ortada, omuz yüksekliklerinin ortası); iki kol da yetişmeli. Dönen: en kötü ulaşılabilirlik oranı (≤1 uygun)."""
    ka, kb = kneel_drops(des_a, des_b)                                      # çizimdeki ile aynı çömelme
    pa = dict(_standing(xa), crouch=ka); pb = dict(_standing(xb), crouch=kb)
    sa = side_a or ("R" if xb > xa else "L"); sb = side_b or ("R" if xa > xb else "L")
    ax, ah = shoulder_offset(des_a, pa, sa); bx, bh = shoulder_offset(des_b, pb, sb)
    worst = 0.0
    for span in (0.0, None):       # nesne boyu burada bilinmez: uzaklık hedef yüksekliğinde dışbükey olduğundan iki uç, her ara aralığı sınırlar
        ga, gb = grip_points(des_a, (xa + ax, ah), des_b, (xb + bx, bh), span)
        ra = math.hypot(ga[0] - (xa + ax), ga[1] - ah) / (des_a["height"] * 0.27)
        rb = math.hypot(gb[0] - (xb + bx), gb[1] - bh) / (des_b["height"] * 0.27)
        worst = max(worst, ra, rb)
    return worst


def meeting_point(des_a, sh_a, des_b, sh_b):
    """Buluşma noktası: omuzlar arası doğru üzerinde, kol boylarıyla orantılı (kısa kollu çocuk daha az, uzun kollu yetişkin daha çok uzanır). sh_*: (dünya x, yükseklik)."""
    la, lb = des_a["height"] * 0.27, des_b["height"] * 0.27
    f = la / (la + lb)
    return sh_a[0] + (sh_b[0] - sh_a[0]) * f, sh_a[1] + (sh_b[1] - sh_a[1]) * f


def hand_offset(des, pose, side):
    """Elin ayağa göre konumu METRE olarak: (dx, yükseklik). Çizimle aynı geometri (ppm=1); nesne ele gerçekten bağlansın diye.
    side: 'L' | 'R' (ekranda sol/sağ el, ön görünüşte). Profilde puppet_side kullanılır."""
    if view_of(pose) == "side":
        import puppet_side
        return puppet_side.hand_offset(des, pose, side)
    Hh = des["height"]; cls = des["class"]
    leg_h = Hh * {"infant": 0.20, "toddler": 0.24, "child": 0.28, "adult": 0.38}[cls]
    torso_h = Hh * {"infant": 0.22, "toddler": 0.25, "child": 0.27, "adult": 0.30}[cls]
    torso_w = Hh * {"infant": 0.30, "toddler": 0.28, "child": 0.25, "adult": 0.22}[cls] * des.get("build", 1.0)
    sq_ = float(pose.get("sq", 1.0)); jump = pose["z"]; sit = max(0.0, -pose["z"])
    squash = (1.0 + max(0.0, jump) / (Hh * 3.0)) * sq_
    torso_w /= max(0.7, sq_) ** 0.5
    bturn = max(-1.0, min(1.0, pose.get("yaw", 0.0) * 1.25)); torso_w *= 1.0 - 0.30 * abs(bturn)
    by = -jump; torso_top = by - leg_h - sit - torso_h * squash + crouch_of(des, pose)
    sg = -1 if side == "L" else 1
    fwd, out = pose["aL"] if side == "L" else pose["aR"]
    ang = abs(out) * 1.0 if out * (1 if side == "L" else -1) >= 0 else -abs(out) * 0.4
    ang = max(-0.5, ang)
    ln = Hh * 0.27 * (1.0 - 0.28 * min(1.0, abs(fwd) / 1.3))
    if ("d" + side) in pose:
        ln = min(Hh * 0.27, pose["d" + side])
    shx, shy = sg * torso_w * 0.52, torso_top + torso_h * 0.14
    return shx + sg * math.sin(ang) * ln, -(shy + math.cos(ang) * ln)


def draw_grip(cv, des, pose, side, fx, fy, ppm):
    """Elin nesneyi kavradığı parmak katmanı: nesne çizildikten SONRA, elin gerçek konumunda 3 kısa parmak + başparmak üstte çizilir (nesne parmakların arkasında kalır)."""
    dx, h = hand_offset(des, pose, side)
    x, y = fx + dx * ppm, fy - h * ppm
    Hh = des["height"] * ppm; r = Hh * 0.052; ow = max(2.0, Hh * 0.012); skin = des["skin"]
    sg = -1 if side == "L" else 1
    if view_of(pose) == "side":
        d = 1.0 if pose.get("yaw", 0.0) >= 0 else -1.0
        for i in range(3):
            cv.capsule((x - d * r * 0.1, y - r * 0.5 + i * r * 0.5), (x + d * r * 0.85, y - r * 0.45 + i * r * 0.5), r * 0.19, r * 0.17, skin, INK, ow * 0.6)
        return
    for i in range(3):
        cv.capsule((x - sg * r * 0.05, y - r * 0.55 + i * r * 0.5), (x + sg * r * 0.95, y - r * 0.45 + i * r * 0.5), r * 0.19, r * 0.17, skin, INK, ow * 0.6)
    cv.capsule((x - sg * r * 0.2, y - r * 0.8), (x + sg * r * 0.5, y - r * 0.95), r * 0.21, r * 0.18, skin, INK, ow * 0.6)       # başparmak üstte


# ---------------------------------------------------------------- yüz penceresi (saç / şapka / örtü gözleri kapatamaz)
EYE_WIDEN_MAX = 1.2       # gözün en çok büyüdüğü oran (şaşkınlık); pencere ifadeye göre OYNAMAZ, saç zıplamaz
EYE_GAP_OW = 0.75         # göz üst kenarı ile örtünün alt kenarı arasındaki pay (dış çizgi kalınlığının katı)


def window_top(eye_y, ery_rest, ow):
    """Ön saç, şapka ve örtünün inebileceği en alt ekran y'si. ery_rest: ifadesiz göz yarıçapı."""
    return eye_y - ery_rest * EYE_WIDEN_MAX - ow * EYE_GAP_OW


def above(pts, limit, cx, half):
    """Göz sütunundaki (|x - cx| <= half) köşeleri pencere çizgisinin üstüne al; yan tutamlar ve diken uçları yerinde kalır."""
    return [(x, min(y, limit) if abs(x - cx) <= half else y) for x, y in pts]


BROW_REST_K = 2.0         # şapka/örtü kenarı: göz merkezinin bu kadar (ifadesiz göz yarıçapı) üstünde, yani dinlenen kaşın üstünde durur


def headwear_edge(eye_y, ery_rest, brow_width, ow):
    """Başlığın (şapka, bere, örtü) göz sütununda inebileceği en alt ekran y'si. Saçtan farklı olarak başlık kaşın üstüne oturur."""
    return eye_y - ery_rest * BROW_REST_K - brow_width * 0.5 - ow * 0.5


def dome(cv, cx, cy, rx, ry, a0, a1, limit, n=24):
    """Tepe yayı (a0..a1, pi..2pi arası): alt kirişi pencere çizgisinin altına inecekse yay daha yukarıda başlar/biter (kubbe başın içinde kalır)."""
    low = (limit - cy) / ry                                    # izin verilen en büyük sin
    if low < 0:
        rise = math.asin(min(1.0, -low))
        a0, a1 = max(a0, math.pi + rise), min(a1, 2 * math.pi - rise)
    return [(x, min(y, limit)) for x, y in cv.arc_pts(cx, cy, rx, ry, a0, a1, n)]


COVER_HALF_K = 0.50       # göz sütununun yarı genişliği / baş genişliği (tam dönük yüzde dış göz buraya uzanır)
BROW_CONTRAST = 60        # örtünün üstündeki kaşın örtüden, tenden ve dış çizgiden en az bu kadar (en büyük kanal farkı) ayrışması istenir
BROW_SKIN_CONTRAST = 44   # açık yüzdeki kaşın tenden en az bu kadar ayrışması istenir


def _contrast(a, b):
    return max(abs(a[i] - b[i]) for i in range(3))


def brow_colour(base, under, skin, over=True):
    """Kaş rengi. Her durumda tenden ayrışır (koyu tende saç renginden türetilen kaş tenle birleşip kayboluyordu). over: kaş bir örtünün üstüne
    düşüyorsa ayrıca örtü renklerinden (under) ve koyu dış çizgiden de ayrışır. Tasarımın kendi kaş rengi yetiyorsa o kalır."""
    grounds = [(skin, BROW_SKIN_CONTRAST)] + ([(g, BROW_CONTRAST) for g in list(under) + [skin, INK]] if over else [])
    score = lambda c: min(_contrast(c, g) - need for g, need in grounds)           # >= 0: bütün zeminlerden yeterince ayrışıyor
    if score(base) >= 0:
        return base
    mix = lambda a, b: tuple((a[i] + b[i]) // 2 for i in range(3))
    # yalnız doğal tonlar (kaşın kendi rengi ve ten): başlık renginden ya da doygunlaştırmadan aday üretilmez
    cands = [shade(base, k) for k in (0.55, 0.7, 1.35)] + [mix(base, skin)] + [shade(skin, k) for k in (0.82, 0.70, 0.55, 0.40, 1.45, 1.75, 2.1, 2.5)]
    good = [c for c in cands if score(c) >= 0]
    return min(good, key=lambda c: _contrast(c, base)) if good else max([base] + cands, key=score)


FACE_LINE_LUM = 48        # ağız, kapalı göz ve burun çizgisinin tenden en az bu kadar parlaklık farkı (0-255) olur


def luma(c):
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


def face_line(skin, base):
    """Yüz çizgisi rengi. Tasarımın rengi tenden ayrışıyorsa aynen kalır; yoksa önce aynı rengin koyusu, o da yetmiyorsa (çok koyu ten)
    tenin açık tonu kullanılır. Renk farkı değil parlaklık farkı ölçülür: koyu mor çizgi koyu kahve tende renkçe ayrı ama gözle seçilmez."""
    ok = lambda c: abs(luma(c) - luma(skin)) >= FACE_LINE_LUM
    for c in (base, shade(base, 0.6), shade(base, 0.3)):
        if ok(c):
            return c
    for k in (1.7, 2.0, 2.3, 2.7, 3.2):
        if ok(shade(skin, k)):
            return shade(skin, k)
    return (235, 215, 200)


def cover_colours(des):
    """Alnı örtebilen parçaların renkleri (kaşın altına gelebilecek zeminler)."""
    out = []
    if des.get("accessory") in ("hat", "beanie"):
        out.append(des["accent"])
    if des.get("hair_style") == "hijab":
        out.append(des.get("scarf", des["hair"]))
    elif des.get("hair_style") != "bald":
        out.append(des["hair"])
    return out


SHADOW = (60, 110, 50)


def ground_shadow(cv, fx, fy, Hh, jump):
    """Ayak altı yer gölgesi: her görünüşte (ön, üç-çeyrek, profil) gövdeden ÖNCE çizilir; zeminde kalır, zıplayınca daralır."""
    cv.ellipse(fx, fy + Hh * 0.012, Hh * 0.30 * (1 - min(0.5, max(0.0, jump) / (Hh * 1.5))), Hh * 0.05, shade(SHADOW, 0.8), None, 0)


HIP_HALF_K = 0.24            # ön / üç-çeyrek görünüşte kalçanın gövde ortasından yarı açıklığı (gövde genişliğinin katı)


def leg_lines(pose, fx, fy, Hh, leg_h, torso_h, torso_w, torso_bot, jump, sit):
    """Ön / üç-çeyrek bacakların çizim noktaları: {'L'|'R': (kalça, ayak)} (ekran px).
    Ayakların ekran sırası kalçalarınkine ters dönmek üzereyken (yana yürüyüşte öne geçen ayak öbür kalçanın ayağını geçer) kalçalar
    gövde ortasında birleşir: bacaklar ters V olur, birbirinin içinden geçip X çizmez. Ayak noktaları değişmez (basılı ayak kaymaz)."""
    feet = {}
    for side, sg in (("L", -1), ("R", 1)):
        swing = pose["lL"] if side == "L" else pose["lR"]
        lift = max(0.0, swing) * leg_h * 0.28
        x0 = fx + sg * torso_w * HIP_HALF_K
        if sit > 1:
            feet[side] = (x0 + sg * torso_w * 0.15, fy - Hh * 0.01 - lift)
        elif ("f" + side) in pose:      # mesafeye bağlı adım: temas ayağı dünyada sabit
            feet[side] = (x0 + pose["f" + side] * Hh, fy - Hh * 0.01 - pose["h" + side] * Hh - max(0, jump))
        else:
            feet[side] = (x0 + swing * leg_h * 0.22 * sg * 0.3, fy - Hh * 0.01 - lift - max(0, jump))
    top_y = torso_bot if sit > 1 else torso_bot - torso_h * 0.04
    # ayakların sırası, iki bacak ortak tepeden çıksa kısa bacağın ayağı hizasında ölçülür: kalkık (kısa) bacak da hesaba girer.
    # Bu fark >= 0 ise kalçalar ne kadar açık olursa olsun bacaklar kesişmez; < 0 ise yalnız ortak tepe (open_k = 0) kesişmesizdir.
    low = min(feet["L"][1], feet["R"][1])
    reach = {s: (feet[s][0] - fx) * (max(1e-6, low - top_y) / max(1e-6, feet[s][1] - top_y)) for s in "LR"}
    open_k = max(0.0, min(1.0, (reach["R"] - reach["L"]) / (2.0 * torso_w * HIP_HALF_K)))
    return {side: ((fx + sg * torso_w * HIP_HALF_K * open_k, top_y), feet[side]) for side, sg in (("L", -1), ("R", 1))}


def draw_character(cv, des, pose, st, fx, fy, ppm, t=0.0):
    """fx,fy: ayak ortası (ekran px). ppm: piksel/metre. st: {'mouth':harf,'blink':0/1,'emotion':str,'dir':-1..1}"""
    if view_of(pose) == "side":
        import puppet_side
        return puppet_side.draw_profile(cv, des, pose, st, fx, fy, ppm, t, sys.modules[__name__])
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
    bturn = max(-1.0, min(1.0, pose.get("yaw", 0.0) * 1.25))   # gövde dönüşü: yürürken/dönerken üç-çeyrek görünüm
    torso_w *= 1.0 - 0.30 * abs(bturn)                          # dönen gövde ekrana daha dar bakar
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

    ground_shadow(cv, fx, fy, Hh, jump)

    cr = crouch_of(des, pose) * ppm      # çömelme: kalça ve üst gövde alçalır, ayaklar yerinde kalır
    hip_y = by - leg_h + cr
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
    legs_ = leg_lines(pose, fx, fy, Hh, leg_h, torso_h, torso_w, torso_bot, jump, sit)
    for side, sg in (("L", -1), ("R", 1)):
        top, foot = legs_[side]
        lw = des.get("lowerwear", "shorts"); lc = des.get("lower_color", shorts)
        if cr > 0.5 and sit <= 1 and lw != "skirt":      # bükülü bacak: uyluk + baldır, diz dışa
            knee = _knee(top, (foot[0], foot[1] - Hh * 0.025), leg_h, sg)
            knee = ((top[0] + foot[0]) / 2 + (knee[0] - (top[0] + foot[0]) / 2) * KNEE_FRONT_K, knee[1])      # ön görünüş: diz izleyiciye doğru bükülür (yana açılma kısalır)
            ankle = (foot[0], foot[1] - Hh * 0.025)
            if lw == "pants":
                cv.capsule(top, knee, Hh * 0.058, Hh * 0.052, lc, INK, ow); cv.capsule(knee, ankle, Hh * 0.052, Hh * 0.047, lc, INK, ow)
            else:
                cv.capsule(top, knee, Hh * 0.045, Hh * 0.042, skin, INK, ow); cv.capsule(knee, ankle, Hh * 0.042, Hh * 0.040, skin, INK, ow)
                cv.capsule(top, ((top[0] + knee[0]) / 2, (top[1] + knee[1]) / 2), Hh * 0.055, Hh * 0.050, shorts, INK, ow)
        elif lw == "pants":      # yetişkin: bacak tamamen pantolon
            cv.capsule(top, (foot[0], foot[1] - Hh * 0.025), Hh * 0.058, Hh * 0.047, lc, INK, ow)
        elif lw == "skirt":    # uzun etek/elbise: bacak görünmez, yalnız ayak ucu
            pass
        else:
            cv.capsule(top, (foot[0], foot[1] - Hh * 0.03), Hh * 0.045, Hh * 0.04, skin if species != "hedgehog" else skin, INK, ow)
            cv.capsule(top, ((top[0] + foot[0]) / 2, (top[1] + foot[1]) / 2 - Hh * 0.01), Hh * 0.055, Hh * 0.05, shorts, INK, ow)
        cv.ellipse(foot[0] + sg * Hh * 0.025 * (1 - abs(bturn)) + bturn * Hh * 0.045, foot[1], Hh * 0.075 * (1 + 0.15 * abs(bturn)), Hh * 0.04, shade(des["accent"], 0.9), INK, ow)
    # ---- gövde
    tpts = [(fx - torso_w * 0.5, torso_top + torso_h * 0.10), (fx - torso_w * 0.36, torso_top), (fx + torso_w * 0.36, torso_top),
            (fx + torso_w * 0.5, torso_top + torso_h * 0.10), (fx + torso_w * 0.55, torso_bot), (fx - torso_w * 0.55, torso_bot)]
    cv.poly_cel(tpts, shirt, INK, ow)
    if des.get("lowerwear") == "skirt":
        sk_top = torso_bot - torso_h * 0.10; ank = by - Hh * 0.05
        cv.poly([(fx - torso_w * 0.55, sk_top), (fx + torso_w * 0.55, sk_top), (fx + torso_w * 0.95, ank), (fx - torso_w * 0.95, ank)], shirt, INK, ow)
    if des.get("pregnant"):
        cv.ellipse(fx + torso_w * 0.12, torso_top + torso_h * 0.70, torso_w * 0.46, torso_h * 0.36, shade(shirt, 1.04), INK, ow)
    cv.ellipse(fx + bturn * torso_w * 0.30, torso_top + torso_h * 0.52, torso_w * 0.13 * (1 - 0.3 * abs(bturn)), torso_w * 0.13, des["accent"], INK, ow * 0.7)
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
        bent = ("d" + side) in pose                                  # yönlü uzanma: gerçek dirsek bükülmesi (kısa menzilde kol kısalmaz, bükülür)
        if bent:
            ln = min(arm_len, pose["d" + side] * ppm)
        hand = (sh[0] + sg * math.sin(ang) * ln, sh[1] + math.cos(ang) * ln)
        if bent and ln < arm_len * 0.985:
            elb = _elbow(sh, hand, arm_len, sg)
            cv.capsule(sh, elb, Hh * 0.036, Hh * 0.032, skin, INK, ow); cv.capsule(elb, hand, Hh * 0.032, Hh * 0.030, skin, INK, ow)
            cv.capsule(sh, ((sh[0] + elb[0]) / 2, (sh[1] + elb[1]) / 2), Hh * 0.045, Hh * 0.040, shirt, INK, ow)
        else:
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
    limit = window_top(eye_y, ery, ow)                                     # ifadeden bağımsız
    hw_limit = headwear_edge(eye_y, ery, ow * 1.7 * des.get("brow_w", 1.0), ow)
    eyes_x = {}
    covered = des["accessory"] in ("hat", "beanie", "glasses") or des["hair_style"] != "bald" or des["species"] == "hedgehog"
    ink_ = face_line(skin, INK)                                            # kapalı göz ve ağız çizgisi
    brows, reach = [], {-1: 0.0, 1: 0.0}                                   # reach: gözlerin baş merkezinden iki yana uzanışı (px)
    if emo == "surprise":
        erx *= 1.12; ery *= 1.2
    hide = st.get("hide", ())          # yalnız ölçüm: yüz öğesini çizmeden aynı kare (face_visibility.py)
    for sg in (-1, 1):
        cx = hx + sg * ex * (1.0 - 0.16 * abs(face)) + face * head_w * 0.19
        far = (sg * face) < -0.2
        rx = erx * (0.82 if far else 1.0)
        eyes_x[sg] = cx
        reach[sg] = max(reach[sg], sg * (cx - hx) + rx)
        if "eyes" in hide:
            pass
        elif st.get("blink") or (emo == "laugh" and not st.get("eyes_open")):
            cv.line(cv.arc_pts(cx, eye_y + ery * 0.1, rx, ery * 0.6, math.pi * 1.1, math.pi * 1.9), ink_, ow * 1.1) if emo == "laugh" else \
                cv.line([(cx - rx, eye_y + ery * 0.15), (cx + rx, eye_y + ery * 0.15)], ink_, ow * 1.2)
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
        if "brows" not in hide:
            brows.append((pts_, shade(hair, 0.85) if species != "hedgehog" else hair, bw_, covered and min(y_ for _x, y_ in pts_) - bw_ * 0.5 < limit))
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
    nl_ = lambda k_: face_line(skin, shade(skin, k_))                        # burun çizgisi tenden ayrışır
    if "nose" in hide:
        pass
    elif species == "hedgehog":
        cv.ellipse(hx + face * head_w * 0.17, head_cy + head_h * 0.10, head_w * 0.075, head_h * 0.06, (40, 30, 30), None, 0)
    else:
        nx_, ny_ = hx + face * head_w * 0.22, head_cy + head_h * 0.08; nt_ = des.get("nose", "line")
        if nt_ == "dot":
            cv.ellipse(nx_, ny_ + head_h * 0.02, head_w * 0.022, head_h * 0.022, nl_(0.72), None, 0)
        elif nt_ == "button":
            cv.ellipse(nx_, ny_ + head_h * 0.015, head_w * 0.04, head_h * 0.035, shade(skin, 0.95), nl_(0.64), 1.6)
        elif nt_ == "round":
            cv.ellipse(nx_, ny_ + head_h * 0.02, head_w * 0.062, head_h * 0.05, shade(skin, 0.94), nl_(0.6), 2.0)
        elif nt_ == "long":
            cv.line([(nx_ - face * head_w * 0.01, ny_ - head_h * 0.12), (nx_, ny_ + head_h * 0.02)], nl_(0.66), 2.2)
            cv.line(cv.arc_pts(nx_, ny_ + head_h * 0.03, head_w * 0.05, head_h * 0.035, 0.2, math.pi - 0.2), nl_(0.62), 2.6)
        else:
            cv.line(cv.arc_pts(nx_, ny_, head_w * 0.035, head_h * 0.04, 0.3, math.pi - 0.3), nl_(0.62), 2.6)
    # ağız
    mouth_letter = st.get("mouth", "X")
    if emo == "laugh" and mouth_letter == "X":
        mouth_letter = "D"
    if "mouth" not in hide:
        draw_mouth(cv, hx + face * head_w * 0.20, head_cy + head_h * 0.26, head_w * 0.26 * des.get("mouth_w", 1.0), head_h * 0.16, mouth_letter, ink_, emo, skin=skin)
    if des.get("dimple"):
        cv.line(cv.arc_pts(hx + face * head_w * 0.14 + head_w * 0.17, head_cy + head_h * 0.27, head_w * 0.03, head_h * 0.03, -1.2, 1.2), shade(skin, 0.6), 2.4)
    # ---- saç (ön)
    top = head_cy - head_h * 0.50
    if style in ("short", "bob", "ponytail", "bun", "wavy_long", "curly", "bangs") and species != "hedgehog":
        pts = cv.arc_pts(hx, head_cy, head_w * 0.545, head_h * 0.54, math.pi * 1.0, math.pi * 2.0, 24)
        fr = [(hx + head_w * 0.54, head_cy - head_h * 0.18), (hx + head_w * 0.36, head_cy - head_h * 0.34), (hx + head_w * 0.16, head_cy - head_h * 0.27),
              (hx - head_w * 0.04, head_cy - head_h * 0.38), (hx - head_w * 0.26, head_cy - head_h * 0.28), (hx - head_w * 0.54, head_cy - head_h * 0.18)]
        cv.poly(above(pts + fr, limit, hx, head_w * COVER_HALF_K), hair, INK, ow)
        if style == "bun":
            cv.ellipse(hx, top - head_h * 0.06, head_w * 0.17, head_w * 0.15, hair, INK, ow)
    if style in ("bob", "bangs") and des.get("class") in ("toddler", "child") and des["female"]:   # küt kâhkül
        cv.poly(above([(hx - head_w * 0.52, head_cy - head_h * 0.20), (hx - head_w * 0.30, head_cy - head_h * 0.08), (hx + head_w * 0.30, head_cy - head_h * 0.08),
                       (hx + head_w * 0.52, head_cy - head_h * 0.20), (hx + head_w * 0.40, head_cy - head_h * 0.45), (hx - head_w * 0.40, head_cy - head_h * 0.45)], limit, hx, head_w * COVER_HALF_K), hair, INK, ow * 0.8)
    if des.get("hat_kind") == "beanie":
        pass
    if style == "spiky" and species != "hedgehog":
        for i in range(7):
            a = math.radians(205 + i * 21.6)
            b = (hx + math.cos(a) * head_w * 0.45, head_cy + math.sin(a) * head_h * 0.50)
            tip = (hx + math.cos(a) * head_w * 0.66, head_cy + math.sin(a) * head_h * 0.72)
            perp = head_w * 0.09
            up_ = max(0.0, b[1] - limit)                            # alçaktaki diken bütün olarak yukarı kayar (yassılaşıp başın dışına çizgi bırakmaz)
            cv.poly([(b[0] - perp, b[1] - up_), (tip[0], tip[1] - up_), (b[0] + perp, b[1] - up_)], hair, INK, ow * 0.8)
        cv.poly(dome(cv, hx, head_cy, head_w * 0.5, head_h * 0.5, math.pi * 1.08, math.pi * 1.92, limit, 16), hair, INK, ow * 0.8)
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
        # dönen yüzde göz o yana kayar: açıklık o yanda gözü içine alacak kadar genişler (dış çizginin içinde kalır)
        wide_ = {sg_: min(head_w * 0.585, max(head_w * 0.46, reach[sg_] + ow)) / (head_w * 0.46) for sg_ in (-1, 1)}
        inner = [(hx + (x_ - hx) * wide_[1 if x_ >= hx else -1], y_) for x_, y_ in inner]
        inner = [(x_, min(y_, hw_limit if abs(x_ - hx) <= head_w * 0.34 else limit) if -reach[-1] - ow <= x_ - hx <= reach[1] + ow else y_) for x_, y_ in inner]
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
    if acc == "glasses":      # çerçeve çizilen gözün merkezini izler (yüz dönünce kaymaz) ve gözü içine alır
        gw = max(erx * 1.45, erx + ow * 1.2)
        gr = min(gw, max(erx + ow * 0.7, (eyes_x[1] - eyes_x[-1]) / 2 - ow * 0.2))       # iki cam üst üste binmez, ama göz dışarıda kalmaz
        for sg in (-1, 1):
            cv.line(cv.arc_pts(eyes_x[sg], eye_y, gr, ery * 1.2 + ow * 0.5, 0, 2 * math.pi, 28), INK, ow)
        if eyes_x[-1] + gr < eyes_x[1] - gr:
            cv.line([(eyes_x[-1] + gr, eye_y), (eyes_x[1] - gr, eye_y)], INK, ow)
    if acc == "hat":
        brim_y = min(top + head_h * 0.06, hw_limit - head_h * 0.10)
        cv.ellipse(hx, brim_y, head_w * 0.62, head_h * 0.10, shade(des["accent"], 0.85), INK, ow)
        cv.poly(cv.arc_pts(hx, brim_y, head_w * 0.42, head_h * 0.42, math.pi, 2 * math.pi, 20), des["accent"], INK, ow)
    if acc == "beanie":       # ayıcık kulaklı bere
        bc = des["accent"]
        for sg in (-1, 1):
            cv.ellipse(hx + sg * head_w * 0.36, top + head_h * 0.02, head_w * 0.11, head_w * 0.11, bc, INK, ow)
            cv.ellipse(hx + sg * head_w * 0.36, top + head_h * 0.03, head_w * 0.05, head_w * 0.05, shade(bc, 0.8), None, 0)
        cv.poly(dome(cv, hx, head_cy - head_h * 0.02, head_w * 0.56, head_h * 0.65, math.pi * 1.0, math.pi * 2.0, hw_limit), bc, INK, ow)
    if acc == "bow":
        cv.ellipse(hx - head_w * 0.38, top + head_h * 0.1, head_w * 0.12, head_w * 0.08, des["accent"], INK, ow)
        cv.ellipse(hx - head_w * 0.22, top + head_h * 0.1, head_w * 0.12, head_w * 0.08, des["accent"], INK, ow)
    for pts_, col_, bw_, over_ in brows:                    # saç, şapka ve gözlükten sonra: kaş her tasarımda okunur
        cv.line(pts_, brow_colour(col_, cover_colours(des), skin, over_), bw_)
