# -*- coding: utf-8 -*-
"""AHOS efekt katmanı: gerçek 2D çizgi filmlerde olup bizde olmayan 'yaşam' katmanları (yalnız PIL; numpy varsa hızlanır).
- icons(): eylem metninden duygu simgeleri (kalp, uyku zzz, şaşkınlık '!', parıltı, müzik notası, ter damlası) karakterin başının üstünde, yumuşak zıplayarak.
- post(): ortam parçacıkları (polen/toz, yaprak/çiçek yaprağı), güneş ışığı huzmesi, sahne geçişi (iris açılış), kapanışta karartma.
Hepsi t'ye bağlı ve deterministiktir (aynı kare her seferinde aynı çıkar; çok işlemcili render ile uyumlu)."""
import math, re
from PIL import Image, ImageDraw, ImageFilter

ICON_RULES = [
    (r"sarıl|kucak|öp|seviş|sevgi|kalp", "heart"),
    (r"uyu|uykuda|mışıl|mırıltı|beşik", "zzz"),
    (r"şaşır|irkil|hay aksi|fark eder|aniden", "exclaim"),
    (r"ışılda|parla|yıldız|harika|bayram|alkış|kutla", "sparkle"),
    (r"şarkı|ıslık|dans|hoplar|neşe", "note"),
    (r"telaş|panik|yetişemez|kaçır", "sweat"),
]


def _h(*a):
    h = 2166136261
    for v in a:
        h = ((h ^ (int(v * 977) & 0xFFFFFFFF)) * 16777619) & 0xFFFFFFFF
    return h / 4294967295.0


def kinds_for(text):
    t = str(text).lower(); out = []
    for pat, k in ICON_RULES:
        if re.search(pat, t) and k not in out:
            out.append(k)
    return out[:2]


def _heart(d, x, y, r, col=(235, 70, 100)):
    d.ellipse([x - r, y - r, x, y + r * 0.2], fill=col); d.ellipse([x, y - r, x + r, y + r * 0.2], fill=col)
    d.polygon([(x - r * 0.98, y - r * 0.15), (x + r * 0.98, y - r * 0.15), (x, y + r * 1.15)], fill=col)


def _star(d, x, y, r, col=(255, 224, 70)):
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5; rr = r if i % 2 == 0 else r * 0.42
        pts.append((x + math.cos(a) * rr, y + math.sin(a) * rr))
    d.polygon(pts, fill=col, outline=(70, 45, 20))


def icons(cv, cam, beat, xs, heights, t, lt):
    """Karakter başlarının üstünde duygu simgeleri. cv: pp.Cv (süper-örnekli tuval), cam: sc.Cam."""
    ks = beat.get("icons") or []
    if not ks or not xs:
        return
    s = cam.s; ss = cv.ss
    d = cv.d
    pop = min(1.0, lt / 0.25)                                   # pop-in
    bounce = 1.0 + 0.08 * math.sin(t * 7.0)
    for k_i, kind in enumerate(ks):
        for i, (x, hgt) in enumerate(zip(xs, heights)):
            if kind == "zzz" and hgt > 0.9:                      # uyku yalnız bebeklerde
                continue
            if kind in ("heart", "sparkle") and i > 1:
                continue
            wx = cam.x(x) * ss + (i * 0.1 + k_i * 0.35) * s * ss * 0.3
            wy = cam.y(hgt * 1.12 + 0.18 + 0.05 * math.sin(t * 3 + i)) * ss
            r = 0.085 * s * ss * pop * bounce
            if kind == "heart":
                for j in range(3):
                    ph = (t * 0.7 + j / 3.0 + _h(i, j)) % 1.0
                    _heart(d, wx + math.sin(ph * 6 + j) * r, wy - ph * 0.5 * s * ss, r * (0.7 + 0.4 * (1 - ph)) * (1 - ph * 0.5))
            elif kind == "zzz":
                for j in range(3):
                    ph = (t * 0.45 + j / 3.0) % 1.0
                    sz = 0.05 * s * ss * (0.6 + ph)
                    xx, yy = wx + ph * 0.25 * s * ss, wy - ph * 0.42 * s * ss
                    d.text((xx, yy), "Z", fill=(70, 90, 170), font=None)
                    d.line([(xx, yy), (xx + sz, yy), (xx, yy + sz), (xx + sz, yy + sz)], fill=(70, 90, 170), width=max(2, int(ss * 2)))
            elif kind == "exclaim" and lt < 1.4:
                a = min(1.0, lt / 0.12) * (1 - max(0.0, (lt - 0.9) / 0.5))
                bw = 0.055 * s * ss * a
                d.rounded_rectangle([wx - bw, wy - 0.28 * s * ss * a, wx + bw, wy - 0.07 * s * ss * a], radius=bw, fill=(240, 60, 50), outline=(70, 20, 20), width=max(2, ss * 2))
                d.ellipse([wx - bw * 0.9, wy - 0.045 * s * ss * a, wx + bw * 0.9, wy + 0.04 * s * ss * a], fill=(240, 60, 50), outline=(70, 20, 20), width=max(2, ss * 2))
            elif kind == "sparkle":
                for j in range(4):
                    ph = (t * 1.3 + j * 0.25 + _h(i, j, 7)) % 1.0
                    sx = wx + (_h(j, i, 3) - 0.5) * 0.7 * s * ss; sy = wy + (_h(j, i, 5) - 0.5) * 0.35 * s * ss
                    _star(d, sx, sy, 0.045 * s * ss * math.sin(ph * math.pi))
            elif kind == "note":
                for j in range(2):
                    ph = (t * 0.6 + j * 0.5) % 1.0
                    nx, ny = wx + (j - 0.5) * 0.3 * s * ss + math.sin(ph * 5) * 0.04 * s * ss, wy - ph * 0.4 * s * ss
                    rr = 0.03 * s * ss
                    d.ellipse([nx - rr, ny - rr * 0.7, nx + rr, ny + rr * 0.7], fill=(60, 60, 110))
                    d.line([(nx + rr, ny), (nx + rr, ny - rr * 3.4)], fill=(60, 60, 110), width=max(2, int(ss * 2)))
            elif kind == "sweat":
                ph = (t * 0.9 + i * 0.3) % 1.0
                sx, sy = wx + 0.12 * s * ss, wy + 0.1 * s * ss + ph * 0.18 * s * ss
                rr = 0.026 * s * ss
                d.ellipse([sx - rr, sy - rr, sx + rr, sy + rr * 1.6], fill=(150, 205, 255), outline=(50, 90, 150))


def _particles(im, kind, t, seed, n=22):
    w, h = im.size
    ov = Image.new("RGBA", im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    for i in range(n):
        r0, r1, r2 = _h(i, seed, 1), _h(i, seed, 2), _h(i, seed, 3)
        sp = 0.015 + 0.03 * r2
        if kind == "pollen":                                     # içeride toz/polen: yavaş süzülür, parlar
            x = (r0 + t * sp * 0.6 + 0.04 * math.sin(t * 0.7 + i)) % 1.0 * w
            y = (r1 - t * sp * 0.5 + 0.03 * math.cos(t * 0.5 + i * 2)) % 1.0 * h
            a = int(70 + 70 * (0.5 + 0.5 * math.sin(t * 1.6 + i)))
            rr = 1.5 + 2.8 * r2
            d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=(255, 250, 220, a))
        else:                                                    # dışarıda yaprak/çiçek yaprağı: çapraz süzülür
            x = (r0 + t * sp * 1.6 + 0.02 * math.sin(t * 1.3 + i)) % 1.0 * w
            y = (r1 + t * sp * 1.1) % 1.0 * h
            ang = t * (1.5 + r2 * 2) + i
            ln = 3 + 3.5 * r2
            col = (255, 200, 215, 130) if i % 3 == 0 else (150, 200, 110, 110)
            dx, dy = math.cos(ang) * ln, math.sin(ang) * ln * 0.45
            d.ellipse([x - abs(dx), y - abs(dy) - 2, x + abs(dx), y + abs(dy) + 2], fill=col)
    return Image.alpha_composite(im.convert("RGBA"), ov).convert("RGB")


def _rays(im, t, strength):
    w, h = im.size
    ov = Image.new("RGBA", im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    for i in range(4):
        x0 = w * (0.05 + 0.27 * i) + 18 * math.sin(t * 0.4 + i)
        wd = w * 0.08
        a = int(26 * strength * (0.7 + 0.3 * math.sin(t * 0.6 + i * 1.7)))
        d.polygon([(x0, 0), (x0 + wd, 0), (x0 + wd + w * 0.28, h), (x0 + w * 0.2, h)], fill=(255, 245, 200, a))
    ov = ov.filter(ImageFilter.GaussianBlur(14))
    return Image.alpha_composite(im.convert("RGBA"), ov).convert("RGB")


def _iris(im, p):
    """Sahne açılışı: daire büyüyerek görüntüyü açar (klasik çizgi film geçişi). p: 0..1"""
    w, h = im.size
    r = (math.hypot(w, h) / 2) * (0.04 + 0.96 * p ** 0.8)
    mask = Image.new("L", im.size, 0); ImageDraw.Draw(mask).ellipse([w / 2 - r, h / 2 - r, w / 2 + r, h / 2 + r], fill=255)
    bg = Image.new("RGB", im.size, (30, 24, 40))
    return Image.composite(im, bg, mask.filter(ImageFilter.GaussianBlur(2)))


def post(im, beat, t, lt, dur, total_s=480.0, first_of_scene=False):
    light = str(beat.get("light") or "").lower()
    outdoor = beat.get("scene") in ("garden", "path", "village", "park", "stage")
    seed = int(beat.get("i", 0)) // 6
    im = _particles(im, "leaf" if outdoor else "pollen", t, seed, n=0 if outdoor else 22)
    if re.search(r"güneş|sabah|öğle|parlak|altın", light):
        im = _rays(im, t, 1.0 if outdoor else 1.4)
    if first_of_scene and lt < 0.55:
        im = _iris(im, lt / 0.55)
    if t > total_s - 1.2:
        k = max(0.0, min(1.0, (total_s - t) / 1.2))
        im = Image.blend(Image.new("RGB", im.size, (20, 16, 26)), im, k)
    return im


# ---------------------------------------------------------------- ayak tozu
# Toz bir ZAMAN SAYACINDAN değil, çizilen pozlardan doğar: bir ayak yere bastığı anda, bastığı yerde bir bulutçuk çıkar, dünyada orada kalır ve söner.
# Ayrıca gövdenin o anki hızıyla kapılanır: karakter yavaşladıkça küçülür, durunca hiç çizilmez.
DUST_V_OFF, DUST_V_FULL = 0.04, 0.16      # gövde hızı (boy/sn): bunun altında toz yok / bunun üstünde tam boy
DUST_LIFE = {"walk": 0.34, "run": 0.42}   # bulutçuğun ömrü (sn)
DUST_R = {"walk": 0.036, "run": 0.062}    # en büyük yarıçap / boy
DUST_HEEL = 0.07                          # bulutçuk ayak merkezinin bu kadar (boy) gerisinden, topuktan çıkar
DUST_DT = 1.0 / 96                        # basış anını arama adımı (sn); parça saatine sabitli: aynı basış her karede aynı anı verir
DUST_SPEED_WIN = 1.0 / 24                 # gövde hızının geriye dönük ölçüm penceresi (sn)


def dust_plan(m, lt, dur, H):
    """Plan hareketi m'nin lt anındaki tozu: {'puffs': [(x, y, yarıçap, yaş01)], 'gate': 0..1, 'dir': ±1, 'run': bool, 'travelled': m}.
    Konumlar dünya metresi (zemin y=0). Yürüyüş/koşu parçası dışında (varış sonrası eylem, taşıma, bekleme) boştur."""
    import shot_motion as sm
    seg, t_, d_ = sm.segment(m, lt, dur)
    out = {"puffs": [], "gate": 0.0, "dir": 1.0, "run": seg["kind"] == "run", "travelled": 0.0, "x": 0.0}
    kind = seg["kind"]
    if kind not in DUST_LIFE or abs(seg["x1"] - seg["x0"]) <= 0.05:
        return out

    def pose(t):
        return sm.pose_at(kind, t, d_, seg.get("seed", 0), seg["x0"], seg["x1"], H, H * 0.45)

    out["dir"] = direction = 1.0 if seg["x1"] >= seg["x0"] else -1.0
    now = pose(t_)
    out["x"] = now["x"]
    out["travelled"] = abs(now["x"] - seg["x0"])
    speed = abs(now["x"] - pose(max(0.0, t_ - DUST_SPEED_WIN))["x"]) / DUST_SPEED_WIN / H
    gate = sm.smooth((speed - DUST_V_OFF) / (DUST_V_FULL - DUST_V_OFF))
    out["gate"] = gate
    if gate <= 0.0:
        return out
    life = DUST_LIFE[kind]
    k0 = max(0, int((t_ - life) / DUST_DT))
    prev = pose(k0 * DUST_DT)
    for k in range(k0 + 1, int(t_ / DUST_DT + 1e-6) + 1):
        cur = pose(k * DUST_DT)
        age = (t_ - k * DUST_DT) / life
        for side in "LR":
            if prev.get("h" + side, 0.0) > 0.0 and cur.get("h" + side, 0.0) <= 0.0 and 0.0 <= age < 1.0:      # bu ayak şimdi bastı
                fx = cur["x"] + cur.get("f" + side, 0.0) * H - direction * DUST_HEEL * H
                r = DUST_R[kind] * H * gate * math.sin(math.pi * min(1.0, 0.12 + 0.88 * age)) ** 0.8          # küçük doğar, açılır, SIFIRA söner
                if r > 1e-4:
                    out["puffs"].append((fx - direction * 0.10 * H * age, 0.02 * H + 0.05 * H * age, r, age))
        prev = cur
    return out


def dust(cv, cam, plan, t, H=1.0):
    """dust_plan çıktısını çizer (koşuda hız çizgileri de). Çağıran, dekor parçalarından ÖNCE çizer: toz hedefin/dekorun önünü örtmez."""
    direction = plan["dir"]
    for x, y, r, age in plan["puffs"]:
        col = (int(214 + 22 * age), int(203 + 28 * age), int(178 + 38 * age))
        for dx, dy, k in ((0.0, 0.0, 1.0), (-0.95, -0.15, 0.68), (0.85, -0.25, 0.55)):         # üç loblu bulutçuk (tek düz daire taş gibi okunuyor)
            cv.ellipse(cam.x(x + direction * dx * r), cam.y(y + dy * r), k * r * cam.s, k * r * 0.82 * cam.s, col, None, 0)
    if plan["run"] and plan["gate"] > 0.0:
        far = plan["travelled"]                                   # çizgi, koşulmamış yere uzanmaz
        for k in range(3):
            ly = (0.35 + 0.28 * k) * H
            ph = ((t * 3.1) + k * 0.37) % 1.0
            a = (0.45 + 0.5 * ph) * H
            b = min(a + 0.55 * H * plan["gate"], far)
            if b > a:
                x0 = plan["x"] - direction * a
                cv.line([(cam.x(x0), cam.y(ly)), (cam.x(plan["x"] - direction * b), cam.y(ly))], (255, 255, 255), max(2.0, 0.02 * cam.s))
